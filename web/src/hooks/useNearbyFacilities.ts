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

export function useNearbyFacilities(
  coords: Coordinates | null,
  filters: NearbyFilters = {},
) {
  return useQuery({
    queryKey: ["nearby", coords, filters],
    queryFn: () =>
      api.nearby({
        lat: coords!.lat,
        lng: coords!.lng,
        insurer: filters.insurer,
        service: filters.service,
        specialty: filters.specialty,
        open_now: filters.openNow,
        radius: filters.radius,
      }),
    enabled: coords !== null,
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
