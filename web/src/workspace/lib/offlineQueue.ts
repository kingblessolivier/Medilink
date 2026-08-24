import { del, entries, set } from "idb-keyval"

import type { SyncAction } from "../../api/types"

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

/** A pending action in the shape POST /queue/sync requires.

 * The stored record is camelCase because it is ours; the wire is snake_case
 * because it is Django's. Skipping this conversion is not a style problem: the
 * client used to post the stored object verbatim, every replay came back 400,
 * and so no check-in made during an outage ever reached the server. The
 * backlog was not even lost - it retried forever and never succeeded.
 *
 * `api.syncQueue` is typed against the generated schema, so the compiler now
 * refuses a caller that forgets this.
 */
export function toWire(action: PendingAction): SyncAction {
  return {
    key: action.key,
    type: action.type,
    client_recorded_at: action.clientRecordedAt,
    payload: action.payload,
  }
}
