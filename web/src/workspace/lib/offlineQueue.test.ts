import { beforeEach, describe, expect, it, vi } from "vitest"

/**
 * The offline queue is the one thing at a reception desk that may never fail.
 *
 * idb-keyval is mocked with an in-memory store: the behaviour under test is
 * ordering and durability, not IndexedDB itself.
 */

const store = new Map<string, unknown>()

vi.mock("idb-keyval", () => ({
  set: async (k: string, v: unknown) => {
    store.set(k, v)
  },
  del: async (k: string) => {
    store.delete(k)
  },
  entries: async () => [...store.entries()],
}))

const { dequeue, enqueue, newKey, pending, pendingCount, toWire } =
  await import("./offlineQueue")

function action(minutesAgo: number, name: string) {
  return {
    key: newKey(),
    type: "check_in" as const,
    clientRecordedAt: new Date(Date.now() - minutesAgo * 60_000).toISOString(),
    payload: { walk_in_name: name },
  }
}

beforeEach(() => {
  store.clear()
})

describe("offlineQueue", () => {
  it("keeps actions until they are explicitly cleared", async () => {
    const first = action(10, "A")
    await enqueue(first)

    expect(await pendingCount()).toBe(1)

    await dequeue(first.key)
    expect(await pendingCount()).toBe(0)
  })

  it("returns actions oldest first, whatever order they were queued in", async () => {
    // The server replays in this order, which is what stops a receptionist
    // who was offline for ten minutes pushing their patients to the back.
    await enqueue(action(5, "Second"))
    await enqueue(action(25, "First"))
    await enqueue(action(1, "Third"))

    const names = (await pending()).map(
      (a) => (a.payload as { walk_in_name: string }).walk_in_name,
    )

    expect(names).toEqual(["First", "Second", "Third"])
  })

  it("issues a distinct key per action", async () => {
    // The key doubles as the Idempotency-Key. A collision would silently drop
    // a patient from the queue.
    const keys = new Set(Array.from({ length: 200 }, () => newKey()))
    expect(keys.size).toBe(200)
  })

  it("ignores unrelated keys in the same store", async () => {
    store.set("medilink.something-else", { not: "an action" })
    await enqueue(action(5, "A"))

    expect(await pendingCount()).toBe(1)
  })
})

describe("the wire shape", () => {
  /**
   * This is not a formatting preference. The client used to post the stored
   * record verbatim - `clientRecordedAt` - to an endpoint that requires
   * `client_recorded_at`. Every replay came back 400, forever, so no check-in
   * made during an outage ever reached the server, and nothing failed loudly
   * enough to notice.
   */
  it("uses the field names the server actually requires", () => {
    const stored = {
      key: newKey(),
      type: "check_in" as const,
      clientRecordedAt: "2026-08-24T09:15:00.000Z",
      payload: { service: "general_consultation", walk_in_name: "Uwase Alice" },
    }

    const wire = toWire(stored)

    expect(wire).toEqual({
      key: stored.key,
      type: "check_in",
      client_recorded_at: "2026-08-24T09:15:00.000Z",
      payload: { service: "general_consultation", walk_in_name: "Uwase Alice" },
    })
    expect(wire).not.toHaveProperty("clientRecordedAt")
  })

  it("keeps the timestamp the receptionist recorded, not a fresh one", () => {
    // The server orders the replayed batch on this. Regenerating it would put
    // an hour of offline patients behind everyone checked in since.
    const recorded = "2026-08-24T08:00:00.000Z"

    const wire = toWire({
      key: newKey(),
      type: "check_in",
      clientRecordedAt: recorded,
      payload: {},
    })

    expect(wire.client_recorded_at).toBe(recorded)
  })
})
