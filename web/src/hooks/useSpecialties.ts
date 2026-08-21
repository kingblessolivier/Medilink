import { useQuery } from "@tanstack/react-query"
import { api } from "../api/client"

/** The clinical vocabulary. Changes rarely; cache it hard. */
export function useSpecialties() {
  return useQuery({
    queryKey: ["specialties"],
    queryFn: api.specialties,
    staleTime: 24 * 60 * 60 * 1000,
  })
}
