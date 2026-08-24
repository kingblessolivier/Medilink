import { useQuery } from "@tanstack/react-query"
import { api } from "../api/client"
import type { ProviderFilters } from "../api/types"

// Declared once, next to the other wire types, so the API client and the hook
// cannot drift apart. `language` was `string` here and a four-value choice on
// the server.
export type { ProviderFilters }

export function useProviders(filters: ProviderFilters = {}, enabled = true) {
  return useQuery({
    queryKey: ["providers", filters],
    queryFn: () => api.providers(filters),
    enabled,
    staleTime: 5 * 60_000,
  })
}
