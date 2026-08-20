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
export type Insurer = Schemas["Insurer"]
export type ServiceType = Schemas["ServiceType"]
export type QueueEntryPublic = Schemas["QueueEntryPublic"]
export type Specialty = Schemas["Specialty"]
export type Provider = Schemas["Provider"]
export type SearchResponse = Schemas["SearchResponse"]
export type SearchGroup = Schemas["SearchGroup"]
export type SearchResult = Schemas["SearchResult"]
export type ProviderList = Schemas["ProviderList"]
export type TriageStatus = Schemas["TriageStatus"]
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
