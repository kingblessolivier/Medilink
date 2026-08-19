import { del, entries, set } from "idb-keyval"

/**
 * Reception check-in is the one operation that may never fail.
 *
 * Every action is written to IndexedDB *first*, then attempted over the
 * network. If the request fails the action simply stays pending, and the whole
 * backlog is replayed through POST /queue/sync when the browser comes back
 * online.
 *
 * `clientRecordedAt` is what preserves fairness: the server orders the replayed
 * batch by this timestamp, so a receptionist who was offline for ten minutes
 * does not push their patients behind everyone checked in since.
 */

export type PendingActionType = "check_in" | "call" | "serve" | "skip" | "cancel"

export type PendingAction = {
  key: string // uuid; doubles as the Idempotency-Key
  type: PendingActionType
  clientRecordedAt: string // ISO - the server sorts on this
  payload: Record<string, unknown>
}

const PREFIX = "pending:"

export function newKey(): string {
  return crypto.randomUUID()
}

export async function enqueue(action: PendingAction): Promise<void> {
  await set(PREFIX + action.key, action)
}

export async function dequeue(key: string): Promise<void> {
  await del(PREFIX + key)
}

export async function pending(): Promise<PendingAction[]> {
  const all = await entries<string, PendingAction>()
  return all
    .filter(([k]) => typeof k === "string" && k.startsWith(PREFIX))
    .map(([, v]) => v)
    .sort((a, b) => a.clientRecordedAt.localeCompare(b.clientRecordedAt))
}

export async function pendingCount(): Promise<number> {
  return (await pending()).length
}
