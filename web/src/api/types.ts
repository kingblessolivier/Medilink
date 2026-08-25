/**
 * App-facing type aliases, DERIVED from the generated OpenAPI schema.
 *
 * `schema.d.ts` is generated - never edit it by hand:
 *     npm run gen:api        (openapi-typescript over backend/schema.yaml)
 *
 * CI regenerates it and fails on any diff, so a backend field rename breaks
 * the build rather than the reception desk. See docs/01 section 9.
 *
 * Everything below is an alias onto a generated type. If you find yourself
 * hand-writing a shape here, fix the backend serializer instead.
 */

import type { components } from "./schema"

type Schemas = components["schemas"]

export type Facility = Schemas["FacilityNearby"]
export type NearbyResponse = Schemas["NearbyResponse"]
export type FacilityDetail = Schemas["FacilityDetail"]
export type OpeningHours = Schemas["OpeningHours"]
export type ServiceBrief = Schemas["ServiceBrief"]
export type ServiceCoverage = Schemas["ServiceCoverage"]
export type Insurer = Schemas["Insurer"]
export type ServiceType = Schemas["ServiceType"]
export type QueueEntryPublic = Schemas["QueueEntryPublic"]
export type Specialty = Schemas["Specialty"]
export type Provider = Schemas["Provider"]
export type SearchResponse = Schemas["SearchResponse"]
export type SearchGroup = Schemas["SearchGroup"]
export type SearchResult = Schemas["SearchResult"]
export type ProviderList = Schemas["ProviderList"]
export type ProviderDetail = Schemas["ProviderDetail"]
export type NotificationList = Schemas["NotificationList"]
export type PreferenceList = Schemas["PreferenceList"]
export type TriageStatus = Schemas["TriageStatus"]
export type TriageSession = Schemas["TriageSession"]
export type TriageQuestion = Schemas["TriageQuestion"]
export type Translation = Schemas["Translation"]
export type Appointment = Schemas["Appointment"]
export type SlotDays = Schemas["SlotDays"]
export type SlotDay = Schemas["SlotDay"]
export type Slot = Schemas["Slot"]
export type Patient = Schemas["Patient"]
export type TokenPair = Schemas["TokenPair"]
export type AppointmentStatus = Appointment["status"]
export type QueueStatus = QueueEntryPublic["status"]

/**
 * The four wait states, derived from the schema enum - so a client that
 * forgets to handle one of them fails to compile.
 *
 *   available          live data, sufficient sample  -> "About 40 min"
 *   not_reported       facility runs no reception tool
 *   insufficient_data  runs it, but under the sample gate
 *   closed             facility closed right now
 *
 * There is deliberately no value meaning "estimated": we never guess.
 */
export type WaitStatus = Schemas["WaitStatusEnum"]

export type Wait = Facility["wait"]

export type Coordinates = { lat: number; lng: number }

export type ApiError = { type: string; detail: string; field?: string }

/* ------------------------------------------------------------------ session */

/**
 * What the caller is, from `GET /auth/session`.
 *
 * `null` means they authenticated but there is no surface for them - a Django
 * user who is neither a superuser nor active facility staff. The client says
 * so rather than looping them back to a form that will keep succeeding.
 */
export type Session = Schemas["Session"]
export type SessionKind = NonNullable<Session["kind"]>
export type SignInResponse = Schemas["SignInResponse"]

/* ---------------------------------------------------------------- workspace */

export type Me = Schemas["StaffMe"]
export type StaffService = Schemas["StaffService"]
export type Board = Schemas["Board"]
export type ServiceGroup = Schemas["ServiceGroup"]
export type SyncResult = Schemas["SyncResponse"]
/** One replayed offline action, exactly as the wire wants it.
 *  Snake_case on purpose - this is the payload, not our model. */
export type SyncAction = Schemas["SyncAction"]
export type CheckInResponse = Schemas["CheckInResponse"]
export type StaffAppointment = Schemas["StaffAppointment"]
export type StaffAppointmentList = Schemas["StaffAppointmentList"]
export type FacilityReport = Schemas["FacilityReport"]
export type ScheduleTemplate = Schemas["ScheduleTemplate"]
export type ScheduleTemplateList = Schemas["ScheduleTemplateList"]
/** Create or update one bookable session. Snake_case: this is the wire. */
export type ScheduleTemplateWrite = Schemas["ScheduleTemplateWrite"]
export type FacilityInsurance = Schemas["FacilityInsurance"]
export type FacilityInsurer = Schemas["FacilityInsurer"]
export type InsurerWithCoverage = Schemas["InsurerWithCoverage"]
export type StaffServiceCoverage = Schemas["StaffServiceCoverage"]
/** Matches FacilityServiceInsurer.Coverage exactly. */
export type CoverageLevel = StaffServiceCoverage["coverage"]
export type FacilitySettings = Schemas["FacilitySettings"]
export type OpeningHoursRow = Schemas["OpeningHoursWriteRow"]
export type PatientLookup = Schemas["PatientLookup"]
export type PatientMatch = Schemas["PatientMatch"]

/** Queue entry as the staff board sees it, plus a local-only flag. */
export type QueueRow = Schemas["QueueEntry"] & {
  /** Set while an optimistic row has not yet been confirmed by the server. */
  optimistic?: boolean
}

export type TransitionAction = "call" | "serve" | "skip" | "cancel"
export type AppointmentAction = "arrived" | "served" | "no_show"

/* ----------------------------------------------------------------- platform */

export type AdminOverview = Schemas["AdminOverview"]
export type VerificationQueue = Schemas["VerificationQueue"]
export type PendingFacility = Schemas["PendingFacility"]
export type PendingProvider = Schemas["PendingProvider"]
export type TriageMonitoring = Schemas["TriageMonitoring"]
export type Verified = Schemas["Verified"]

// ------------------------------------------------- platform oversight

export type AdminFacility = Schemas["AdminFacility"]
export type AdminFacilityList = Schemas["AdminFacilityList"]
export type AdminProvider = Schemas["AdminProvider"]
export type AdminProviderList = Schemas["AdminProviderList"]
export type AdminStaff = Schemas["AdminStaff"]
export type AdminStaffList = Schemas["AdminStaffList"]
export type PlatformActivityReport = Schemas["PlatformActivity"]
export type AccessLog = Schemas["AccessLog"]
export type DeliveryReport = Schemas["DeliveryReport"]

/** Query parameters for GET /providers. Mirrors ProviderQuerySerializer. */
export type ProviderFilters = {
  specialty?: string
  facility?: string
  service?: string
  language?: "rw" | "en" | "fr" | "sw"
  search?: string
  limit?: number
}
