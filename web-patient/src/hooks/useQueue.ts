import { useQuery } from "@tanstack/react-query"
import { api } from "../api/client"

/**
 * Polling, not WebSockets. A hospital queue advances roughly 8-15 times an
 * hour; 20-second polling survives a mobile network dropping and returning,
 * which WebSockets handle badly, and needs no extra infrastructure.
 */
export const QUEUE_POLL_MS = 20_000

export function useCurrentQueueEntry(enabled: boolean) {
  return useQuery({
    queryKey: ["queue", "current"],
    queryFn: api.currentQueueEntry,
    enabled,
    refetchInterval: QUEUE_POLL_MS,
    // A cached queue position is actively harmful: it would tell a patient to
    // stay home while they are being called.
    staleTime: 0,
    gcTime: 0,
    retry: 1,
  })
}

export function useQueueEntry(id: number | null) {
  return useQuery({
    queryKey: ["queue", "entry", id],
    queryFn: () => api.queueEntry(id!),
    enabled: id !== null,
    refetchInterval: QUEUE_POLL_MS,
    staleTime: 0,
    gcTime: 0,
    retry: 1,
  })
}

export function useUpcomingAppointments(enabled: boolean) {
  return useQuery({
    queryKey: ["appointments", "upcoming"],
    queryFn: () => api.appointments("upcoming"),
    enabled,
    staleTime: 60_000,
  })
}
