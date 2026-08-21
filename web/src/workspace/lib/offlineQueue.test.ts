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

const { dequeue, enqueue, newKey, pending, pendingCount } = await import(
  "./offlineQueue"
)

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
