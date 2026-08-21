import { useQuery } from "@tanstack/react-query"
import { api } from "../api/client"
import type { Coordinates } from "../api/types"

export type NearbyFilters = {
  insurer?: string
  service?: string
  /** Set by a Care Guide recommendation. `service` always wins over it. */
  specialty?: string
  openNow?: boolean
  radius?: number
}

/**
 * Facilities near a point, or in a district.
 *
 * `district` is an alternative ORIGIN, not an extra filter: it is what a
 * patient gives when their browser will not hand over a location. Results
 * then come back with `distance_m: null`, because there is genuinely no
 * point to measure from.
 */
export function useNearbyFacilities(
  coords: Coordinates | null,
  filters: NearbyFilters = {},
  district?: string | null,
) {
  const origin = coords
    ? { lat: coords.lat, lng: coords.lng }
    : district
      ? { district }
      : null

  return useQuery({
    queryKey: ["nearby", origin, filters],
    queryFn: () =>
      api.nearby({
        ...origin!,
        insurer: filters.insurer,
        service: filters.service,
        specialty: filters.specialty,
        open_now: filters.openNow,
        radius: filters.radius,
      }),
    enabled: origin !== null,
    // A facility list does not change minute to minute.
    staleTime: 60_000,
    // Keep for a day so the offline fallback has something to show.
    gcTime: 24 * 60 * 60 * 1000,
    retry: 2,
  })
}

export function useInsurers() {
  return useQuery({
    queryKey: ["insurers"],
    queryFn: api.insurers,
    staleTime: 24 * 60 * 60 * 1000, // changes perhaps twice a year
  })
}

export function useServiceTypes() {
  return useQuery({
    queryKey: ["service-types"],
    queryFn: api.serviceTypes,
    staleTime: 24 * 60 * 60 * 1000,
  })
}

export function useDistricts() {
  return useQuery({
    queryKey: ["districts"],
    queryFn: api.districts,
    staleTime: 24 * 60 * 60 * 1000,
  })
}
