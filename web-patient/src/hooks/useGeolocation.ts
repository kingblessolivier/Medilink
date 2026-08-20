import { useCallback, useState } from "react"

// Same bounds as the backend serializer. Rejecting out-of-bounds coordinates
// on the client avoids a guaranteed 400 round trip.
const RWANDA = { lat: [-2.92, -1.02], lng: [28.8, 30.95] } as const

export type GeoState =
  | { status: "idle" }
  | { status: "locating" }
  | { status: "ready"; lat: number; lng: number; accuracy: number }
  | { status: "denied" }
  | { status: "unavailable" }
  | { status: "out_of_bounds" }

export function useGeolocation() {
  const [state, setState] = useState<GeoState>({ status: "idle" })

  const locate = useCallback(() => {
    // `"geolocation" in navigator` is TRUE even when the value is undefined,
    // which happens on insecure origins and in some embedded browsers. Probing
    // the callable itself is what actually keeps this from throwing and
    // leaving the patient on a blank screen instead of the district picker.
    const geo =
      typeof navigator !== "undefined" ? navigator.geolocation : undefined
    if (!geo || typeof geo.getCurrentPosition !== "function") {
      setState({ status: "unavailable" })
      return
    }

    setState({ status: "locating" })
    try {
      geo.getCurrentPosition(
        ({ coords }) => {
          const { latitude: lat, longitude: lng, accuracy } = coords
          const inRwanda =
            lat >= RWANDA.lat[0] &&
            lat <= RWANDA.lat[1] &&
            lng >= RWANDA.lng[0] &&
            lng <= RWANDA.lng[1]

          setState(
            inRwanda
              ? { status: "ready", lat, lng, accuracy }
              : { status: "out_of_bounds" },
          )
        },
        (error) =>
          setState({
            status:
              error.code === error.PERMISSION_DENIED ? "denied" : "unavailable",
          }),
        {
          enableHighAccuracy: true,
          timeout: 10_000,
          // Accept a two-minute-old fix. Demanding a fresh high-accuracy fix
          // on a low-end Android phone costs battery and seconds for no
          // benefit - the patient has not moved far.
          maximumAge: 120_000,
        },
      )
    } catch {
      setState({ status: "unavailable" })
    }
  }, [])

  return { state, locate }
}
