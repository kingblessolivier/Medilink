import { act, renderHook, waitFor } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import { useGeolocation } from "./useGeolocation"

/**
 * The geolocation states, including the ones that actually happen.
 *
 * Denied permission and an out-of-Rwanda fix are the two most common real
 * outcomes - desktop browsers, VPNs, and patients who tap "Block". Each must
 * reach the district picker rather than a blank screen.
 */

const KIGALI = { latitude: -1.9536, longitude: 30.0606, accuracy: 20 }
const LONDON = { latitude: 51.5074, longitude: -0.1278, accuracy: 20 }

function mockGeolocation(impl: (success: any, error: any) => void) {
  Object.defineProperty(navigator, "geolocation", {
    value: { getCurrentPosition: impl },
    configurable: true,
  })
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe("useGeolocation", () => {
  it("resolves a Rwandan coordinate", async () => {
    mockGeolocation((success) => success({ coords: KIGALI }))

    const { result } = renderHook(() => useGeolocation())
    act(() => result.current.locate())

    await waitFor(() => expect(result.current.state.status).toBe("ready"))
    expect(result.current.state).toMatchObject({ lat: -1.9536, lng: 30.0606 })
  })

  it("rejects a coordinate outside Rwanda rather than querying for it", async () => {
    // Desktop IP geolocation and VPNs land here constantly. Sending it to the
    // API would earn a guaranteed 400.
    mockGeolocation((success) => success({ coords: LONDON }))

    const { result } = renderHook(() => useGeolocation())
    act(() => result.current.locate())

    await waitFor(() =>
      expect(result.current.state.status).toBe("out_of_bounds"),
    )
  })

  it("reports a denied permission distinctly from an unavailable one", async () => {
    mockGeolocation((_success, error) =>
      error({ code: 1, PERMISSION_DENIED: 1 }),
    )

    const { result } = renderHook(() => useGeolocation())
    act(() => result.current.locate())

    await waitFor(() => expect(result.current.state.status).toBe("denied"))
  })

  it("reports a timeout as unavailable", async () => {
    mockGeolocation((_success, error) =>
      error({ code: 3, PERMISSION_DENIED: 1 }),
    )

    const { result } = renderHook(() => useGeolocation())
    act(() => result.current.locate())

    await waitFor(() => expect(result.current.state.status).toBe("unavailable"))
  })

  it("handles a browser with no geolocation at all", async () => {
    Object.defineProperty(navigator, "geolocation", {
      value: undefined,
      configurable: true,
    })

    const { result } = renderHook(() => useGeolocation())
    act(() => result.current.locate())

    await waitFor(() => expect(result.current.state.status).toBe("unavailable"))
  })
})
