import { useCallback, useEffect, useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { ApiError, api } from "../api/client"
import {
  dequeue,
  enqueue,
  newKey,
  pending,
  type PendingAction,
  type PendingActionType,
} from "../lib/offlineQueue"

/**
 * Every queue mutation goes through here, so the offline path is the default
 * path rather than a special case bolted on afterwards.
 *
 * Order matters:
 *   1. write to IndexedDB
 *   2. attempt the network
 *   3. clear from IndexedDB only once the server has accounted for it
 *
 * The action key doubles as the Idempotency-Key, so a request that times out
 * and is later replayed through /queue/sync cannot create a duplicate entry.
 */
export function useQueueActions() {
  const queryClient = useQueryClient()
  const [online, setOnline] = useState(navigator.onLine)
  const [pendingCount, setPendingCount] = useState(0)
  const [syncing, setSyncing] = useState(false)
  const [lastError, setLastError] = useState<string | null>(null)

  const refreshCount = useCallback(async () => {
    setPendingCount((await pending()).length)
  }, [])

  const invalidateBoard = useCallback(
    () => queryClient.invalidateQueries({ queryKey: ["board"] }),
    [queryClient],
  )

  const flush = useCallback(async () => {
    const backlog = await pending()
    if (backlog.length === 0 || !navigator.onLine) return

    setSyncing(true)
    try {
      const result = await api.sync(backlog)
      // Clear everything the server accounted for, rejections included: a
      // duplicate check-in will never succeed on retry, and leaving it pending
      // would block the backlog forever.
      for (const row of result.results) await dequeue(row.key)

      const failures = result.results.filter((r) => !r.ok)
      setLastError(
        failures.length
          ? `${failures.length} queued action(s) rejected: ${failures[0].error}`
          : null,
      )
      await invalidateBoard()
    } catch (error) {
      setLastError(error instanceof Error ? error.message : "Sync failed")
    } finally {
      setSyncing(false)
      await refreshCount()
    }
  }, [invalidateBoard, refreshCount])

  useEffect(() => {
    refreshCount()
    const goOnline = () => {
      setOnline(true)
      void flush()
    }
    const goOffline = () => setOnline(false)

    window.addEventListener("online", goOnline)
    window.addEventListener("offline", goOffline)
    if (navigator.onLine) void flush()

    return () => {
      window.removeEventListener("online", goOnline)
      window.removeEventListener("offline", goOffline)
    }
  }, [flush, refreshCount])

  /** Record the action durably, then try the network with the same key. */
  const run = useCallback(
    async (
      type: PendingActionType,
      payload: Record<string, unknown>,
      attempt: (key: string, recordedAt: string) => Promise<unknown>,
    ) => {
      const action: PendingAction = {
        key: newKey(),
        type,
        clientRecordedAt: new Date().toISOString(),
        payload,
      }

      await enqueue(action)
      await refreshCount()
      setLastError(null)

      try {
        await attempt(action.key, action.clientRecordedAt)
        await dequeue(action.key)
      } catch (error) {
        if (error instanceof ApiError && error.status >= 400 && error.status < 500) {
          // The server was reachable and refused. Retrying will not help, so
          // drop it and surface the reason to the receptionist.
          await dequeue(action.key)
          setLastError(error.message)
        } else {
          // Network failure. Leave it pending for /queue/sync on reconnect.
          setLastError(null)
        }
      } finally {
        await refreshCount()
        await invalidateBoard()
      }

      return action
    },
    [invalidateBoard, refreshCount],
  )

  const checkIn = useCallback(
    (payload: { service: string; phone?: string; walk_in_name?: string }) =>
      run("check_in", payload, (key, recordedAt) =>
        api.checkIn({ ...payload, client_recorded_at: recordedAt }, key),
      ),
    [run],
  )

  const transition = useCallback(
    (id: number, action: "call" | "serve" | "skip" | "cancel") =>
      run(action, { entry_id: id }, () => api.transition(id, action)),
    [run],
  )

  return {
    online,
    pendingCount,
    syncing,
    lastError,
    clearError: () => setLastError(null),
    checkIn,
    transition,
    flush,
  }
}
