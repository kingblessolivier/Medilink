import type { PendingAction } from "../lib/offlineQueue"
import type {
  AppointmentAction,
  Board,
  CheckInResponse,
  FacilityDetail,
  FacilityReport,
  Me,
  ProviderList,
  StaffAppointment,
  StaffAppointmentList,
  SyncResult,
  TransitionAction,
} from "./types"

const BASE = "/api/v1"
const ACCESS_KEY = "medilink.access"
const REFRESH_KEY = "medilink.refresh"

export type {
  AppointmentAction,
  Board,
  FacilityDetail,
  FacilityReport,
  InsurerBrief,
  Provider,
  ProviderList,
  ServiceBrief,
  StaffAppointment,
  StaffAppointmentList,
  CheckInResponse,
  Me,
  QueueRow,
  QueueStatus,
  ServiceGroup,
  StaffService,
  SyncResult,
  TransitionAction,
} from "./types"

export class ApiError extends Error {
  constructor(
    public status: number,
    public type: string,
    message: string,
  ) {
    super(message)
  }
}

export const tokens = {
  get access() {
    return localStorage.getItem(ACCESS_KEY)
  },
  get refresh() {
    return localStorage.getItem(REFRESH_KEY)
  },
  save(access: string, refresh: string) {
    localStorage.setItem(ACCESS_KEY, access)
    localStorage.setItem(REFRESH_KEY, refresh)
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY)
    localStorage.removeItem(REFRESH_KEY)
  },
}

async function refreshAccess(): Promise<boolean> {
  const refresh = tokens.refresh
  if (!refresh) return false

  const response = await fetch(`${BASE}/auth/token/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh }),
  })
  if (!response.ok) {
    tokens.clear()
    return false
  }
  const body = await response.json()
  tokens.save(body.access, body.refresh ?? refresh)
  return true
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  retryOn401 = true,
): Promise<T> {
  const headers = new Headers(init.headers)
  headers.set("Accept", "application/json")
  if (init.body) headers.set("Content-Type", "application/json")
  const access = tokens.access
  if (access) headers.set("Authorization", `Bearer ${access}`)

  const response = await fetch(BASE + path, { ...init, headers })

  // A twelve-hour shift can outlast an access token; refresh once, silently.
  if (response.status === 401 && retryOn401 && (await refreshAccess())) {
    return request<T>(path, init, false)
  }

  if (!response.ok) {
    let type = "error"
    let detail = response.statusText
    try {
      const body = await response.json()
      type = body.type ?? type
      detail = body.detail ?? detail
    } catch {
      // Non-JSON error body - keep the status text.
    }
    throw new ApiError(response.status, type, detail)
  }

  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const api = {
  async login(username: string, password: string): Promise<void> {
    const body = await request<{ access: string; refresh: string }>(
      "/auth/token",
      { method: "POST", body: JSON.stringify({ username, password }) },
    )
    tokens.save(body.access, body.refresh)
  },

  me: () => request<Me>("/staff/me"),

  board: () => request<Board>("/queue/board"),

  checkIn: (
    payload: {
      service: string
      phone?: string
      walk_in_name?: string
      client_recorded_at?: string
    },
    idempotencyKey: string,
  ) =>
    request<CheckInResponse>("/queue/entries", {
      method: "POST",
      body: JSON.stringify(payload),
      headers: { "Idempotency-Key": idempotencyKey },
    }),

  transition: (id: number, action: TransitionAction) =>
    request<CheckInResponse>(`/queue/entries/${id}/${action}`, { method: "POST" }),

  // ------------------------------------------------------------ workspace

  appointments: (params: { date?: string; status?: string } = {}) => {
    const query = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v) as [string, string][],
    ).toString()
    return request<StaffAppointmentList>(
      "/staff/appointments" + (query ? `?${query}` : ""),
    )
  },

  setAppointmentStatus: (id: number, status: AppointmentAction) =>
    request<StaffAppointment>(`/staff/appointments/${id}/status`, {
      method: "POST",
      body: JSON.stringify({ status }),
    }),

  reports: (days = 30) => request<FacilityReport>(`/staff/reports?days=${days}`),

  // The workspace reads its own facility through the PUBLIC endpoints for
  // doctors and services: it is the same data patients see, and a facility
  // checking how it appears to them is exactly the point of those screens.
  facility: (slug: string) => request<FacilityDetail>(`/facilities/${slug}`),

  facilityProviders: (slug: string) =>
    request<ProviderList>(`/facilities/${slug}/providers`),

  sync: (actions: PendingAction[]) =>
    request<SyncResult>("/queue/sync", {
      method: "POST",
      body: JSON.stringify({
        actions: actions.map((a) => ({
          key: a.key,
          type: a.type,
          client_recorded_at: a.clientRecordedAt,
          payload: a.payload,
        })),
      }),
    }),
}
