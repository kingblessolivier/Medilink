import { useQuery } from "@tanstack/react-query"
import { api } from "../api/client"

export type ProviderFilters = {
  specialty?: string
  facility?: string
  service?: string
  language?: string
  search?: string
  limit?: number
}

export function useProviders(filters: ProviderFilters = {}, enabled = true) {
  return useQuery({
    queryKey: ["providers", filters],
    queryFn: () => api.providers(filters),
    enabled,
    staleTime: 5 * 60_000,
  })
}
