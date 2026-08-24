import type {
  Appointment,
  FacilityDetail,
  Insurer,
  NearbyResponse,
  NotificationList,
  Patient,
  PreferenceList,
  QueueEntryPublic,
  ProviderDetail,
  ProviderList,
  SearchResponse,
  ServiceType,
  Specialty,
  SlotDays,
  TokenPair,
  TriageSession,
  TriageStatus,
  // Unified session
  Session,
  SignInResponse,
  // Workspace
  Me,
  Board,
  CheckInResponse,
  ProviderFilters,
  SyncAction,
  SyncResult,
  TransitionAction,
  StaffAppointment,
  StaffAppointmentList,
  AppointmentAction,
  FacilityReport,
  // Platform
  AdminOverview,
  VerificationQueue,
  TriageMonitoring,
  Verified,
  AdminFacilityList,
  AdminProviderList,
  AdminStaffList,
  PlatformActivityReport,
  AccessLog,
  DeliveryReport,
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
  headers?: Record<string, string>
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
  // Reception's check-in sends an Idempotency-Key; two taps on a slow
  // connection must not queue the same patient twice.
  for (const [key, value] of Object.entries(options.headers ?? {})) {
    headers.set(key, value)
  }
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
    /** With lng. Omit both and give `district` instead. */
    lat?: number
    lng?: number
    district?: string
    radius?: number
    insurer?: string
    service?: string
    specialty?: string
    open_now?: boolean
    limit?: number
  }) => request<NearbyResponse>("/facilities/nearby", { params, auth: false }),

  facility: (slug: string) =>
    request<FacilityDetail>(`/facilities/${slug}`, { auth: false }),

  slots: (slug: string, params: { service: string; provider?: string; date_from?: string }) =>
    request<SlotDays>(`/facilities/${slug}/slots`, { params, auth: false }),

  insurers: () =>
    request<{ results: Insurer[] }>("/insurers", { auth: false }),

  serviceTypes: () =>
    request<{ results: ServiceType[] }>("/service-types", { auth: false }),

  // ---------------------------------------------- platform oversight
  //
  // All superuser-only. `services` answers "is the platform being used?";
  // these answer "what is happening on it, and is anything wrong?".

  adminFacilities: () => request<AdminFacilityList>("/platform/facilities"),

  adminProviders: () => request<AdminProviderList>("/platform/providers"),

  adminStaff: () => request<AdminStaffList>("/platform/staff"),

  adminActivity: (days = 7) =>
    request<PlatformActivityReport>("/platform/activity", { params: { days } }),

  adminAccessLog: (days = 7) =>
    request<AccessLog>("/platform/access-log", { params: { days } }),

  adminDelivery: (days = 7) =>
    request<DeliveryReport>("/platform/delivery", { params: { days } }),

  triageStatus: () => request<TriageStatus>("/triage/status"),

  // Both return 503 until a named clinician has signed off a protocol. That
  // is the gate working, not an outage - the UI must already have hidden the
  // entry point, and treats a 503 here as "not available yet", never as an
  // error to retry. See docs/08 section 8.
  triageStart: () =>
    request<TriageSession>("/triage/sessions", { method: "POST", auth: false }),

  triageAnswer: (sessionId: string, question: string, option: string) =>
    request<TriageSession>(`/triage/sessions/${sessionId}/answer`, {
      method: "POST",
      body: { question, option },
      auth: false,
    }),

  provider: (slug: string) => request<ProviderDetail>(`/providers/${slug}`),

  // Named filters, not `Record<string, unknown>`. An unrecognised query
  // parameter is silently dropped by the serializer, so a typo here would
  // quietly return the unfiltered list rather than fail - the same shape of
  // hole that let `clientRecordedAt` reach an endpoint expecting
  // `client_recorded_at`. These names match ProviderQuerySerializer.
  providers: (params: ProviderFilters = {}) =>
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

  book: (payload: {
    facility: string
    service: string
    /** Omit for the facility general clinic - "any available". */
    provider?: string
    slot_start: string
  }) =>
    request<Appointment>("/appointments", {
      method: "POST",
      body: payload,
    }),

  notifications: () => request<NotificationList>("/me/notifications"),

  notificationPreferences: () =>
    request<PreferenceList>("/me/notification-preferences"),

  updateNotificationPreference: (kind: string, enabled: boolean) =>
    request<PreferenceList>("/me/notification-preferences", {
      method: "PATCH",
      body: { kind, enabled },
    }),

  appointment: (id: number) => request<Appointment>(`/appointments/${id}`),

  cancelAppointment: (id: number) =>
    request<Appointment>(`/appointments/${id}/cancel`, { method: "POST" }),

  // ------------------------------------------------------------------ auth
  //
  // One door for all three kinds of user. The response's `session.kind` is
  // what the client routes on - see App.tsx.

  signIn: (username: string, password: string) =>
    request<SignInResponse>("/auth/login", {
      method: "POST",
      body: { username, password },
      auth: false,
    }),

  register: (payload: {
    username: string
    password: string
    phone: string
    /**
     * One-time code from `requestCode`. Required, and required to be for
     * THIS number: registration writes to whatever patient record already
     * holds it, and USSD, WhatsApp and reception-desk patients all have a
     * blank password. Without the code, knowing a number would be enough to
     * claim that person's visit history. Server returns 401 if it is wrong.
     */
    code: string
    full_name?: string
    /** Required by the server, and required to be true. See docs/08 s6. */
    consent: boolean
  }) =>
    request<SignInResponse>("/auth/register", {
      method: "POST",
      body: payload,
      auth: false,
    }),

  session: () => request<Session>("/auth/session"),

  // ------------------------------------------------------------- workspace

  staffMe: () => request<Me>("/staff/me"),

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
      body: payload,
      headers: { "Idempotency-Key": idempotencyKey },
    }),

  transition: (id: number, action: TransitionAction) =>
    request<CheckInResponse>(`/queue/entries/${id}/${action}`, {
      method: "POST",
    }),

  // `SyncAction[]`, not `unknown[]`. It was `unknown[]`, and that is exactly
  // why nothing caught the client sending `clientRecordedAt` to an endpoint
  // that requires `client_recorded_at` - every replay 400'd, so no check-in
  // made offline ever reached the server. Typed against the generated schema,
  // the compiler now refuses the mismatch.
  syncQueue: (actions: SyncAction[]) =>
    request<SyncResult>("/queue/sync", {
      method: "POST",
      body: { actions },
    }),

  staffAppointments: (params: { date?: string; status?: string } = {}) =>
    request<StaffAppointmentList>("/staff/appointments", { params }),

  setAppointmentStatus: (id: number, status: AppointmentAction) =>
    request<StaffAppointment>(`/staff/appointments/${id}/status`, {
      method: "POST",
      body: { status },
    }),

  staffReports: (days = 30) =>
    request<FacilityReport>("/staff/reports", { params: { days } }),

  facilityProviders: (slug: string) =>
    request<ProviderList>(`/facilities/${slug}/providers`),

  // -------------------------------------------------------------- platform

  overview: (days = 30) =>
    request<AdminOverview>("/platform/overview", { params: { days } }),

  verificationQueue: () =>
    request<VerificationQueue>("/platform/verification"),

  verifyFacility: (id: number, note: string) =>
    request<Verified>(`/platform/verification/facilities/${id}`, {
      method: "POST",
      body: { note },
    }),

  verifyProvider: (id: number, note: string) =>
    request<Verified>(`/platform/verification/providers/${id}`, {
      method: "POST",
      body: { note },
    }),

  triageMonitoring: (days = 30) =>
    request<TriageMonitoring>("/platform/triage-monitoring", {
      params: { days },
    }),
}

/**
 * Types re-exported from ./types.
 *
 * The workspace and platform screens came from apps whose client re-exported
 * its own types, and importing a type from the module you already import the
 * client from is one import line rather than two. Kept rather than rewritten
 * across fifteen files for no behavioural gain.
 */
export type {
  Session,
  SessionKind,
  SignInResponse,
  Me,
  StaffService,
  Board,
  ServiceGroup,
  QueueRow,
  SyncResult,
  CheckInResponse,
  TransitionAction,
  StaffAppointment,
  StaffAppointmentList,
  AppointmentAction,
  FacilityReport,
  ServiceBrief,
  ProviderList,
  AdminOverview,
  VerificationQueue,
  PendingFacility,
  PendingProvider,
  TriageMonitoring,
  Verified,
  AdminFacility,
  AdminFacilityList,
  AdminProvider,
  AdminProviderList,
  AdminStaff,
  AdminStaffList,
  PlatformActivityReport,
  AccessLog,
  DeliveryReport,
} from "./types"
