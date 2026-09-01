import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { ApiRequestError, api } from "./client"

/**
 * The error path is what a patient sees on a bad connection or outside the
 * Rwanda bounds, so it is worth more coverage than the happy path.
 */

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  })

let fetchMock: ReturnType<typeof vi.fn>

beforeEach(() => {
  fetchMock = vi.fn()
  vi.stubGlobal("fetch", fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

function requestedUrl(): URL {
  return new URL(fetchMock.mock.calls[0][0])
}

/** Await a call that must reject, and hand back what it threw. */
async function rejection(promise: Promise<unknown>): Promise<unknown> {
  try {
    await promise
  } catch (error) {
    return error
  }
  throw new Error("Expected the request to reject, but it resolved.")
}

describe("query building", () => {
  it("sends the coordinates and filters it was given", async () => {
    fetchMock.mockResolvedValue(json({ results: [] }))

    await api.nearby({ lat: -1.9536, lng: 30.0606, insurer: "mutuelle" })

    const url = requestedUrl()
    expect(url.pathname).toBe("/api/v1/facilities/nearby")
    expect(url.searchParams.get("lat")).toBe("-1.9536")
    expect(url.searchParams.get("lng")).toBe("30.0606")
    expect(url.searchParams.get("insurer")).toBe("mutuelle")
  })

  it("omits unset filters instead of sending empty ones", async () => {
    fetchMock.mockResolvedValue(json({ results: [] }))

    await api.nearby({ lat: -1.9536, lng: 30.0606, insurer: undefined })

    // `insurer=` would reach the backend as an empty string and match nothing.
    expect(requestedUrl().searchParams.has("insurer")).toBe(false)
  })

  it("sends open_now=false rather than dropping it", async () => {
    fetchMock.mockResolvedValue(json({ results: [] }))

    await api.nearby({ lat: -1.9536, lng: 30.0606, open_now: false })

    expect(requestedUrl().searchParams.get("open_now")).toBe("false")
  })
})

describe("errors", () => {
  it("surfaces the RFC 7807 fields the backend sends", async () => {
    fetchMock.mockResolvedValue(
      json(
        {
          type: "validation_error",
          detail: "lat must be between -2.92 and -1.02 (Rwanda).",
          field: "lat",
        },
        400,
      ),
    )

    const error = (await rejection(
      api.nearby({ lat: 51.5074, lng: -0.1278 }),
    )) as ApiRequestError

    expect(error).toBeInstanceOf(ApiRequestError)
    expect(error.status).toBe(400)
    expect(error.type).toBe("validation_error")
    expect(error.field).toBe("lat")
    // The client shows this text, so it must arrive intact.
    expect(error.message).toContain("Rwanda")
  })

  it("falls back to the status text when the body is not JSON", async () => {
    // A proxy or gateway error page, which has no RFC 7807 body at all.
    fetchMock.mockResolvedValue(
      new Response("<html>502</html>", { status: 502, statusText: "Bad Gateway" }),
    )

    const error = (await rejection(api.districts())) as ApiRequestError

    expect(error.status).toBe(502)
    expect(error.type).toBe("error")
  })

  it("lets a network failure through as-is, so offline is distinguishable", async () => {
    // Offline must not be reported as an API error - the banner and the
    // service-worker cache handle it, and an ApiRequestError would hide that.
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"))

    const error = await rejection(api.districts())

    expect(error).toBeInstanceOf(TypeError)
    expect(error).not.toBeInstanceOf(ApiRequestError)
  })
})
