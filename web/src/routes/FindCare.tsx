import { Suspense, lazy, useCallback, useEffect, useState } from "react"
import { useSearchParams } from "react-router-dom"
import { useI18n } from "../i18n"
import { useGeolocation } from "../hooks/useGeolocation"
import {
  useInsurers,
  useNearbyFacilities,
  useServiceTypes,
} from "../hooks/useNearbyFacilities"
import { useSpecialties } from "../hooks/useSpecialties"
import { useInsurerPreference } from "../hooks/useInsurerPreference"
import { FacilityCard } from "../components/FacilityCard"
import { DistrictPicker } from "../components/DistrictPicker"
import { CachedNotice } from "../components/CachedNotice"
import { Button, Chip, EmptyState, ErrorState, Field, ListSkeleton, Notice, Select, Skeleton } from "../ui"

// The map is the largest dependency in the app. A patient who never opens it
// pays nothing for it.
const FacilityMap = lazy(() => import("../components/FacilityMap"))

/**
 * Find Care - the strongest screen in the product.
 *
 * Desktop is roughly 40% results, 60% map. Mobile is list-first with the map
 * behind a toggle, because on a phone over 3G a list gets somebody to care and
 * a map mostly costs them data.
 *
 * The list and the map are one thing: hovering a card highlights its marker,
 * clicking a marker selects its card. A map and a list that disagree are worse
 * than either alone.
 */
export function FindCare() {
  const { t, lang } = useI18n()
  const [params, setParams] = useSearchParams()
  const { state: geo, locate } = useGeolocation()
  const { insurer, setInsurer } = useInsurerPreference()

  const [selected, setSelected] = useState<string | null>(null)
  const [showMap, setShowMap] = useState(false)

  const service = params.get("service") ?? undefined
  const specialty = params.get("specialty") ?? undefined
  const openNow = params.get("open") === "1"
  // In the URL like every other filter, so a reloaded or shared link
  // reproduces the same list.
  const district = params.get("district") ?? undefined

  useEffect(() => {
    locate()
  }, [locate])

  const coords = geo.status === "ready" ? { lat: geo.lat, lng: geo.lng } : null
  // A real location wins: it gives distances, which a district cannot.
  const query = useNearbyFacilities(
    coords,
    { insurer, service, specialty, openNow },
    district,
  )

  const { data: serviceData } = useServiceTypes()
  const { data: specialtyData } = useSpecialties()
  const { data: insurerData } = useInsurers()
  const insurerName = insurerData?.results.find((i) => i.code === insurer)?.name

  const setParam = useCallback(
    (key: string, value: string | undefined) => {
      const next = new URLSearchParams(params)
      if (value) next.set(key, value)
      else next.delete(key)
      // Filters live in the URL so a patient can share or reload a search.
      setParams(next, { replace: true })
    },
    [params, setParams],
  )

  const results = query.data?.results ?? []
  const geoFailed =
    geo.status === "denied" ||
    geo.status === "unavailable" ||
    geo.status === "out_of_bounds"

  const label = (item: { name_rw: string; name_en: string; name_fr: string }) =>
    lang === "rw" ? item.name_rw : lang === "fr" ? item.name_fr : item.name_en

  return (
    <div className="ml-page py-4">
      <h1 className="sr-only">{t("find_care")}</h1>

      {/* A recommendation arrived from the Care Guide. Say so, and make it
          removable - the patient is not trapped in it. */}
      {specialty && (
        <div className="mb-4">
          <Notice tone="info">
            {t("filtered_by_specialty", {
              specialty:
                specialtyData?.results.find((s) => s.code === specialty)?.name_en ??
                specialty,
            })}{" "}
            <button
              className="underline"
              onClick={() => setParam("specialty", undefined)}
            >
              {t("clear")}
            </button>
          </Notice>
        </div>
      )}

      <div className="grid gap-5 lg:grid-cols-[minmax(0,42fr)_minmax(0,58fr)]">
        {/* ------------------------------------------------ results column */}
        <div className="min-w-0">
          <div className="ml-card mb-4 grid gap-3 p-4 sm:grid-cols-2">
            <Field label={t("filter_service")}>
              {(id) => (
                <Select
                  id={id}
                  value={service ?? ""}
                  onChange={(e) => setParam("service", e.target.value || undefined)}
                >
                  <option value="">{t("all_services")}</option>
                  {(serviceData?.results ?? []).map((s) => (
                    <option key={s.code} value={s.code}>
                      {label(s)}
                    </option>
                  ))}
                </Select>
              )}
            </Field>

            <Field label={t("filter_insurer")}>
              {(id) => (
                <Select
                  id={id}
                  value={insurer ?? ""}
                  onChange={(e) => setInsurer(e.target.value || undefined)}
                >
                  <option value="">{t("no_cover_set")}</option>
                  {(insurerData?.results ?? []).map((i) => (
                    <option key={i.code} value={i.code}>
                      {i.name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>

            <label className="flex min-h-touch items-center gap-2 sm:col-span-2">
              <input
                type="checkbox"
                className="ml-checkbox"
                checked={openNow}
                onChange={(e) => setParam("open", e.target.checked ? "1" : undefined)}
              />
              <span className="text-body">{t("filter_open_now")}</span>
            </label>
          </div>

          <div className="mb-3 flex items-center justify-between">
            {/* An h2, not a styled paragraph. This heads the results list,
                and without it the page jumped H1 -> H3 - the only screen in
                the product that skipped a level. */}
            <h2 className="text-h3">
              {query.data ? t("n_results", { n: query.data.count }) : " "}
            </h2>
            {/* Mobile only: the map is opt-in, never the default. */}
            <Button
              size="sm"
              variant="tertiary"
              className="lg:hidden"
              onClick={() => setShowMap((v) => !v)}
            >
              {showMap ? t("hide_map") : t("show_map")}
            </Button>
          </div>

          {geoFailed && (
            <div className="mb-4">
              <DistrictPicker
                message={
                  geo.status === "out_of_bounds"
                    ? t("out_of_bounds")
                    : t("location_denied")
                }
                selected={district}
                onPick={(picked) => setParam("district", picked)}
                onRetry={locate}
              />
            </div>
          )}

          <div className="mb-3 empty:mb-0">
            <CachedNotice updatedAt={query.dataUpdatedAt} />
          </div>

          {query.data?.query.radius_expanded && (
            <div className="mb-3">
              <Notice tone="warning">
                {t("radius_expanded", {
                  original: 5,
                  actual: Math.round(query.data.query.radius / 1000),
                })}
              </Notice>
            </div>
          )}

          {(geo.status === "locating" || query.isLoading) && <ListSkeleton rows={4} />}

          {query.isError && (
            <ErrorState
              title={t("error_generic")}
              action={
                <Button size="sm" onClick={() => query.refetch()}>
                  {t("retry")}
                </Button>
              }
            />
          )}

          {query.data && results.length === 0 && (
            <EmptyState
              title={t("no_results")}
              body={t("no_results_body")}
              action={
                <Button
                  size="sm"
                  onClick={() => {
                    setParams(new URLSearchParams(), { replace: true })
                    setInsurer(undefined)
                  }}
                >
                  {t("clear_filters")}
                </Button>
              }
            />
          )}

          <div className="space-y-3">
            {results.map((facility) => (
              <FacilityCard
                key={facility.id}
                facility={facility}
                insurerName={insurerName}
                selected={selected === facility.slug}
                onHighlight={setSelected}
              />
            ))}
          </div>
        </div>

        {/* ---------------------------------------------------- map column */}
        <div
          className={
            (showMap ? "block " : "hidden ") +
            "lg:sticky lg:top-4 lg:block lg:h-[calc(100vh-6rem)]"
          }
        >
          <div className="h-[60vh] lg:h-full">
            {results.length > 0 ? (
              <Suspense fallback={<Skeleton className="h-full w-full rounded-xl" />}>
                <FacilityMap
                  facilities={results}
                  center={coords}
                  selectedSlug={selected}
                  onSelect={setSelected}
                />
              </Suspense>
            ) : (
              <div className="ml-card grid h-full place-items-center p-6 text-center">
                <p className="text-body text-ink-muted">{t("map_needs_results")}</p>
              </div>
            )}
          </div>

          {selected && (
            <div className="mt-2 lg:absolute lg:inset-x-3 lg:bottom-3 lg:mt-0">
              {results
                .filter((f) => f.slug === selected)
                .map((facility) => (
                  <div key={facility.id} className="shadow-overlay rounded-xl">
                    <FacilityCard facility={facility} insurerName={insurerName} selected />
                  </div>
                ))}
            </div>
          )}
        </div>
      </div>

      {specialty && results.length > 0 && (
        <p className="mt-4 text-small text-ink-muted">
          <Chip tone="info">{t("from_care_guide")}</Chip>
        </p>
      )}
    </div>
  )
}
