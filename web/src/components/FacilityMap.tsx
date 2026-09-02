import { useEffect, useRef, useState } from "react"
import type { Map as MapLibreMap, Marker } from "maplibre-gl"
import { useI18n } from "../i18n"
import type { Coordinates, Facility } from "../api/types"

/**
 * The map.
 *
 * Three constraints shape this component, all of them from docs/04:
 *
 * 1. **The list is the product; the map assists it.** This is rendered behind
 *    a lazy import so a patient on 3G who never opens the map pays nothing for
 *    it - MapLibre plus its stylesheet is larger than the entire rest of the
 *    app.
 * 2. **Free tiles only.** A key-metered commercial API is not a dependency
 *    this project can carry.
 * 3. **Selection is two-way.** Hovering a card highlights its marker; clicking
 *    a marker selects its card. A map and a list that disagree are worse than
 *    either alone.
 */

/**
 * A minimal raster style over OpenStreetMap tiles.
 *
 * Defined inline rather than fetched: MapLibre's demotiles style carries only
 * low-zoom country outlines, so at the city zoom a patient actually needs it
 * renders as empty blue.
 *
 * BEFORE LAUNCH: move to a self-hosted or contracted tile source. The OSM
 * community servers are volunteer-funded with a usage policy that a
 * production health service should not lean on.
 */
const RASTER_STYLE = {
  version: 8 as const,
  sources: {
    osm: {
      type: "raster" as const,
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      maxzoom: 19,
      attribution: "(c) OpenStreetMap contributors",
    },
  },
  layers: [{ id: "osm", type: "raster" as const, source: "osm" }],
}

type Props = {
  facilities: Facility[]
  center: Coordinates | null
  selectedSlug: string | null
  onSelect: (slug: string | null) => void
}

export default function FacilityMap({
  facilities,
  center,
  selectedSlug,
  onSelect,
}: Props) {
  const { t } = useI18n()
  const container = useRef<HTMLDivElement>(null)
  const map = useRef<MapLibreMap | null>(null)
  const markers = useRef<Record<string, Marker>>({})
  // The map is created asynchronously behind a dynamic import. Without a
  // readiness flag the marker effect runs first, finds no map, returns
  // early, and never re-runs - so no markers ever appear.
  const [ready, setReady] = useState(false)

  // Create once. Re-creating a map on every render is the classic way to
  // make a phone very hot.
  useEffect(() => {
    if (!container.current || map.current) return
    let cancelled = false

    void (async () => {
      const maplibre = await import("maplibre-gl")
      await import("maplibre-gl/dist/maplibre-gl.css")
      if (cancelled || !container.current) return

      map.current = new maplibre.Map({
        container: container.current,
        style: RASTER_STYLE,
        center: center ? [center.lng, center.lat] : [30.0606, -1.9536],
        zoom: 12,
        attributionControl: { compact: true },
      })
      map.current.addControl(new maplibre.NavigationControl(), "top-right")
      setReady(true)
    })()

    return () => {
      cancelled = true
      map.current?.remove()
      map.current = null
      setReady(false)
    }
    // Deliberately empty: the map is created once and then updated below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Markers follow the result list.
  useEffect(() => {
    const instance = map.current
    if (!instance) return
    let cancelled = false

    void (async () => {
      const maplibre = await import("maplibre-gl")
      if (cancelled) return

      for (const marker of Object.values(markers.current)) marker.remove()
      markers.current = {}

      for (const facility of facilities) {
        const el = document.createElement("button")
        el.type = "button"
        // Markers are real buttons: keyboard reachable, and announced.
        el.setAttribute("aria-label", facility.name)
        el.className = "ml-marker"
        el.dataset.slug = facility.slug
        el.addEventListener("click", (event) => {
          event.stopPropagation()
          onSelect(facility.slug)
        })

        markers.current[facility.slug] = new maplibre.Marker({ element: el })
          .setLngLat([facility.location.lng, facility.location.lat])
          .addTo(instance)
      }
    })()

    return () => {
      cancelled = true
    }
  }, [facilities, onSelect, ready])

  // Frame the results. A fixed zoom either crops them or strands the
  // patient in empty space when the nearest facility is far away.
  useEffect(() => {
    const instance = map.current
    if (!instance || facilities.length === 0) return

    void (async () => {
      const maplibre = await import("maplibre-gl")
      const bounds = new maplibre.LngLatBounds()
      for (const f of facilities) bounds.extend([f.location.lng, f.location.lat])
      if (center) bounds.extend([center.lng, center.lat])
      instance.fitBounds(bounds, { padding: 64, maxZoom: 15, duration: 0 })
    })()
  }, [facilities, center, ready])

  // Selection: highlight the marker and bring it into view.
  useEffect(() => {
    for (const [slug, marker] of Object.entries(markers.current)) {
      marker.getElement().dataset.selected = String(slug === selectedSlug)
    }
    if (!selectedSlug || !map.current) return

    const facility = facilities.find((f) => f.slug === selectedSlug)
    if (facility) {
      map.current.easeTo({
        center: [facility.location.lng, facility.location.lat],
        duration: 320,
      })
    }
  }, [selectedSlug, facilities, ready])

  return (
    <div
      ref={container}
      role="application"
      aria-label={t("map_label")}
      className="h-full w-full rounded-lg border border-n200 bg-n100"
    />
  )
}
