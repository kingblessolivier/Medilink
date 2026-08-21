import type { components } from "./schema"

/**
 * Platform admin API client.
 *
 * Deliberately small. Django admin still does CRUD on every model; this client
 * only reaches the three things it cannot - the verification workflow,
 * platform aggregates, and triage monitoring.
 *
 * There is no patient endpoint here, and there is not one to add: the backend
 * exposes a patient COUNT and nothing else. See apps/platform_admin/services.py.
 */

type Schemas = components["schemas"]

export type AdminOverview = Schemas["AdminOverview"]
export type VerificationQueue = Schemas["VerificationQueue"]
export type PendingFacility = Schemas["PendingFacility"]
export type PendingProvider = Schemas["PendingProvider"]
export type TriageMonitoring = Schemas["TriageMonitoring"]
export type Verified = Schemas["Verified"]

const BASE = "/api/v1"
// Namespaced away from the other two apps: an admin and a receptionist may
// well use the same browser, and a shared key would sign one out of the other
// or - worse - carry an admin token into the reception app.
const ACCESS_KEY = "medilink.admin.access"
const REFRESH_KEY = "medilink.admin.refresh"
// Kept because the access token does NOT carry one: SimpleJWT issues
// `user_id` and nothing else. A label in a sidebar, never authorisation.
const USERNAME_KEY = "medilink.admin.username"

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
  get username() {
    return localStorage.getItem(USERNAME_KEY) ?? ""
  },
  save(access: string, refresh: string, username?: string) {
    localStorage.setItem(ACCESS_KEY, access)
    localStorage.setItem(REFRESH_KEY, refresh)
    if (username) localStorage.setItem(USERNAME_KEY, username)
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY)
    localStorage.removeItem(REFRESH_KEY)
    localStorage.removeItem(USERNAME_KEY)
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
    tokens.save(body.access, body.refresh, username)
  },

  overview: (days = 30) =>
    request<AdminOverview>(`/platform/overview?days=${days}`),

  verificationQueue: () =>
    request<VerificationQueue>("/platform/verification"),

  verifyFacility: (id: number, note: string) =>
    request<Verified>(`/platform/verification/facilities/${id}`, {
      method: "POST",
      body: JSON.stringify({ note }),
    }),

  verifyProvider: (id: number, note: string) =>
    request<Verified>(`/platform/verification/providers/${id}`, {
      method: "POST",
      body: JSON.stringify({ note }),
    }),

  triageMonitoring: (days = 30) =>
    request<TriageMonitoring>(`/platform/triage-monitoring?days=${days}`),
}
