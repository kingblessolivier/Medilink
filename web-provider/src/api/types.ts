/**
 * App-facing type aliases, DERIVED from the generated OpenAPI schema.
 *
 * `schema.d.ts` is generated - never edit it by hand:
 *     npm run gen:api        (openapi-typescript over backend/schema.yaml)
 *
 * CI regenerates it and fails on any diff, so a backend field rename breaks
 * the build rather than the reception desk. See docs/01 section 9.
 */

import type { components } from "./schema"

type Schemas = components["schemas"]

export type Me = Schemas["StaffMe"]
export type StaffService = Schemas["StaffService"]
export type Board = Schemas["Board"]
export type ServiceGroup = Schemas["ServiceGroup"]
export type SyncResult = Schemas["SyncResponse"]
export type CheckInResponse = Schemas["CheckInResponse"]

/** Queue entry as the staff board sees it, plus a local-only flag. */
export type QueueRow = Schemas["QueueEntry"] & {
  /** Set while an optimistic row has not yet been confirmed by the server. */
  optimistic?: boolean
}

export type QueueStatus = Schemas["QueueEntryStatusEnum"]

export type TransitionAction = "call" | "serve" | "skip" | "cancel"

// ---------------------------------------------------------------- workspace

export type StaffAppointment = Schemas["StaffAppointment"]
export type StaffAppointmentList = Schemas["StaffAppointmentList"]
export type FacilityReport = Schemas["FacilityReport"]
export type FacilityDetail = Schemas["FacilityDetail"]
export type ProviderList = Schemas["ProviderList"]
export type Provider = Schemas["Provider"]
export type ServiceBrief = Schemas["ServiceBrief"]
export type InsurerBrief = Schemas["InsurerBrief"]

/** The three transitions reception performs from the appointment list. */
export type AppointmentAction = "arrived" | "served" | "no_show"
