import { useEffect } from "react"
import { Link } from "react-router-dom"
import { useI18n } from "../i18n"
import { useGeolocation } from "../hooks/useGeolocation"
import { useInsurers, useNearbyFacilities } from "../hooks/useNearbyFacilities"
import { useInsurerPreference } from "../hooks/useInsurerPreference"
import { FacilityCard } from "../components/FacilityCard"
import { InsurerChip } from "../components/InsurerChip"
import { LanguageToggle } from "../components/LanguageToggle"
import { DistrictPicker } from "../components/DistrictPicker"

/**
 * Home screen, State A (nothing active).
 *
 * States B (in a queue) and C (appointment today) arrive in Phase 2, when
 * GET /queue/current exists to select between them. The layout deliberately
 * leaves room for the live card to replace the search hero.
 */
export function Home() {
  const { t } = useI18n()
  const { state: geo, locate } = useGeolocation()
  const { insurer, setInsurer } = useInsurerPreference()
  const { data: insurerData } = useInsurers()

  useEffect(() => {
    locate()
  }, [locate])

  const coords = geo.status === "ready" ? { lat: geo.lat, lng: geo.lng } : null
  const query = useNearbyFacilities(coords, { insurer })
  const insurerName = insurerData?.results.find((i) => i.code === insurer)?.name

  const geoFailed =
    geo.status === "denied" ||
    geo.status === "unavailable" ||
    geo.status === "out_of_bounds"

  return (
    <div className="mx-auto max-w-md px-4 pb-24 pt-4">
      <header className="mb-4 flex items-start justify-between gap-2">
        <p className="text-lg font-semibold">{t("greeting")}</p>
        <LanguageToggle />
      </header>

      {/* Primary action. In State B this is replaced by the live queue card. */}
      <Link to="/search" className="btn-primary mb-3 w-full">
        {t("find_care")}
      </Link>

      <div className="mb-5">
        <InsurerChip insurer={insurer} onChange={setInsurer} />
      </div>

      {geoFailed && (
        <DistrictPicker
          message={
            geo.status === "out_of_bounds"
              ? t("out_of_bounds")
              : t("location_denied")
          }
          onRetry={locate}
        />
      )}

      {(geo.status === "locating" || query.isLoading) && (
        <p className="text-sm text-neutral-500">{t("loading")}</p>
      )}

      {query.isError && (
        <div className="card">
          <p className="text-sm text-danger">{t("error_generic")}</p>
          <button
            className="btn-secondary mt-3 w-full"
            onClick={() => query.refetch()}
          >
            {t("retry")}
          </button>
        </div>
      )}

      {query.data && (
        <section>
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-neutral-500">
            {t("nearby_open")}
          </h2>

          {query.data.query.radius_expanded && (
            <p className="mb-3 rounded-lg bg-amber-50 p-3 text-sm text-warning">
              {t("radius_expanded", {
                original: 5,
                actual: Math.round(query.data.query.radius / 1000),
              })}
            </p>
          )}

          {query.data.results.length === 0 && (
            <p className="text-sm text-neutral-500">{t("no_results")}</p>
          )}

          {query.data.results.slice(0, 3).map((facility) => (
            <FacilityCard
              key={facility.id}
              facility={facility}
              insurerName={insurerName}
            />
          ))}

          {query.data.results.length > 3 && (
            <Link
              to="/search"
              className="block py-2 text-center text-sm text-primary"
            >
              {t("see_all")}
            </Link>
          )}
        </section>
      )}
    </div>
  )
}
