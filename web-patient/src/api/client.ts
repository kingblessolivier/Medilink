import type {
  Appointment,
  FacilityDetail,
  Insurer,
  NearbyResponse,
  Patient,
  QueueEntryPublic,
  ProviderDetail,
  ProviderList,
  SearchResponse,
  ServiceType,
  Specialty,
  SlotDays,
  TokenPair,
  TriageStatus,
} from "./types"

const BASE = "/api/v1"
const ACCESS_KEY = "medilink.access"
const REFRESH_KEY = "medilink.refresh"

export class ApiRequestError extends Error {
  constructor(
    public status: number,
    public type: string,
    message: string,
    public field?: string,
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

type RequestOptions = {
  method?: string
  body?: unknown
  params?: Record<string, unknown>
  auth?: boolean
}

async function request<T>(
  path: string,
  options: RequestOptions = {},
  retryOn401 = true,
): Promise<T> {
  const url = new URL(BASE + path, window.location.origin)
  for (const [key, value] of Object.entries(options.params ?? {})) {
    if (value === undefined || value === null || value === "") continue
    url.searchParams.set(key, String(value))
  }

  const headers = new Headers({ Accept: "application/json" })
  if (options.body !== undefined) headers.set("Content-Type", "application/json")
  if (options.auth !== false && tokens.access) {
    headers.set("Authorization", `Bearer ${tokens.access}`)
  }

  const response = await fetch(url.toString(), {
    method: options.method ?? "GET",
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  })

  if (response.status === 401 && retryOn401 && (await refreshAccess())) {
    return request<T>(path, options, false)
  }

  if (!response.ok) {
    let type = "error"
    let detail = response.statusText
    let field: string | undefined
    try {
      const body = await response.json()
      type = body.type ?? type
      detail = body.detail ?? detail
      field = body.field
    } catch {
      // Non-JSON error body - keep the status text.
    }
    throw new ApiRequestError(response.status, type, detail, field)
  }

  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const api = {
  // --- discovery (public) ---
  nearby: (params: {
    lat: number
    lng: number
    radius?: number
    insurer?: string
    service?: string
    specialty?: string
    open_now?: boolean
    limit?: number
  }) => request<NearbyResponse>("/facilities/nearby", { params, auth: false }),

  facility: (slug: string) =>
    request<FacilityDetail>(`/facilities/${slug}`, { auth: false }),

  slots: (slug: string, params: { service: string; date_from?: string }) =>
    request<SlotDays>(`/facilities/${slug}/slots`, { params, auth: false }),

  insurers: () =>
    request<{ results: Insurer[] }>("/insurers", { auth: false }),

  serviceTypes: () =>
    request<{ results: ServiceType[] }>("/service-types", { auth: false }),

  triageStatus: () => request<TriageStatus>("/triage/status"),

  provider: (slug: string) => request<ProviderDetail>(`/providers/${slug}`),

  providers: (params: Record<string, unknown>) =>
    request<ProviderList>("/providers", { params }),

  specialties: () =>
    request<{ results: Specialty[] }>("/specialties"),

  search: (params: { q: string; lat?: number; lng?: number }) =>
    request<SearchResponse>("/search", { params }),

  districts: () =>
    request<{ results: string[] }>("/districts", { auth: false }),

  // --- auth ---
  requestCode: (phone: string) =>
    request<void>("/auth/otp/request", {
      method: "POST",
      body: { phone },
      auth: false,
    }),

  verifyCode: async (phone: string, code: string) => {
    const body = await request<TokenPair>("/auth/otp/verify", {
      method: "POST",
      body: { phone, code },
      auth: false,
    })
    tokens.save(body.access, body.refresh)
    return body.patient
  },

  // --- patient ---
  me: () => request<Patient>("/me"),

  updateMe: (patch: Partial<Patient>) =>
    request<Patient>("/me", { method: "PATCH", body: patch }),

  /**
   * The home screen calls this on load to choose between state A (nothing
   * active) and state B (in a queue). Resolves to null on 204.
   */
  currentQueueEntry: () =>
    request<QueueEntryPublic | undefined>("/queue/current").then(
      (entry) => entry ?? null,
    ),

  queueEntry: (id: number) =>
    request<QueueEntryPublic>(`/queue/entries/${id}`),

  appointments: (status: "upcoming" | "past" | "all" = "upcoming") =>
    request<Appointment[]>("/appointments", { params: { status } }),

  book: (payload: { facility: string; service: string; slot_start: string }) =>
    request<Appointment>("/appointments", {
      method: "POST",
      body: payload,
    }),

  cancelAppointment: (id: number) =>
    request<Appointment>(`/appointments/${id}/cancel`, { method: "POST" }),
}
