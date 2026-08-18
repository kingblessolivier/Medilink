// Hand-written for Phase 0 bootstrap ONLY.
//
// Replace with generated types before this grows:
//   npm run gen:api        (openapi-typescript against /api/schema/)
// and wire the regeneration into CI, so a backend field rename breaks the
// build rather than the reception desk. See docs/01 section 9.

export type WaitStatus =
  | "available"
  | "not_reported"
  | "insufficient_data"
  | "closed"

export type Wait = {
  status: WaitStatus
  minutes: number | null
  people_waiting: number | null
  as_of: string
}

export type Coordinates = { lat: number; lng: number }

export type Facility = {
  id: number
  slug: string
  name: string
  level: string
  ownership: string
  district: string
  sector: string
  location: Coordinates
  distance_m: number
  phone: string
  is_open: boolean
  opens_at: string | null
  closes_at: string | null
  closing_soon: boolean
  accepts_insurer: boolean
  insurers: string[]
  services: string[]
  wait: Wait
  bookable: boolean
}

export type NearbyResponse = {
  as_of: string
  query: {
    lat: number
    lng: number
    radius: number
    radius_expanded: boolean
    insurer: string | null
    service: string | null
    open_now: boolean
  }
  count: number
  results: Facility[]
}

export type OpeningHours = {
  weekday: number
  opens_at: string
  closes_at: string
}

export type FacilityDetail = {
  id: number
  slug: string
  name: string
  level: string
  ownership: string
  province: string
  district: string
  sector: string
  address: string
  location: Coordinates
  phone: string
  email: string
  is_open: boolean
  opening_hours: OpeningHours[]
  insurers: { code: string; name: string; note: string }[]
  services: { code: string; name_rw: string; name_en: string; name_fr: string }[]
  wait: Wait
  directions_url: string
  verified_at: string | null
}

export type Insurer = { code: string; name: string; is_public: boolean }

export type ServiceType = {
  code: string
  name_rw: string
  name_en: string
  name_fr: string
}

export type ApiError = { type: string; detail: string; field?: string }
