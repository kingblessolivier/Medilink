import { useEffect } from "react"
import { useSearchParams } from "react-router-dom"
import { useI18n } from "../i18n"
import { useGeolocation } from "../hooks/useGeolocation"
import { useInsurers, useNearbyFacilities } from "../hooks/useNearbyFacilities"
import { useInsurerPreference } from "../hooks/useInsurerPreference"
import { FacilityCard } from "../components/FacilityCard"
import { DistrictPicker } from "../components/DistrictPicker"
import {
  Button,
  EmptyState,
  ErrorState,
  ListSkeleton,
  Notice,
} from "../ui"

/**
 * Insurance as a front door, not a filter.
 *
 * Insurance already existed in two places - as a filter on Find Care, and as
 * a tab on a facility page - and in neither could a patient start from it.
 * "Where can I use my Mutuelle" had no answer that begins with the insurance,
 * which is odd given the proposal names insurance uncertainty as one of the
 * four problems MediLink exists to remove.
 *
 * The choice is remembered, because it is the same answer every time. It is
 * the same preference the rest of the app already uses, so picking here also
 * filters Find Care and the home screen.
 *
 * The copy rule holds throughout: this says what a FACILITY accepts, never
 * that a patient is covered. See docs/11 section 7 rule 6.
 */
export function Insurance() {
  const { t } = useI18n()
  const [params, setParams] = useSearchParams()
  const { state: geo, locate } = useGeolocation()
  const { insurer: stored, setInsurer: remember } = useInsurerPreference()

  // The URL wins over the stored preference, so a shared link shows what the
  // sender meant rather than the recipient's own insurer.
  const selected = params.get("insurer") ?? stored ?? ""
  const district = params.get("district") ?? undefined

  // Ask once on mount. Without this `geo.status` stays idle - neither ready
  // nor failed - and the page renders a skeleton that never resolves.
  useEffect(() => {
    locate()
  }, [locate])

  const { data: insurerData } = useInsurers()
  const insurers = insurerData?.results ?? []
  const chosen = insurers.find((i) => i.code === selected)

  const coords = geo.status === "ready" ? { lat: geo.lat, lng: geo.lng } : null
  const nearby = useNearbyFacilities(
    coords,
    { insurer: selected || undefined },
    district,
  )

  const hasOrigin = coords !== null || Boolean(district)

  const choose = (code: string) => {
    const next = new URLSearchParams(params)
    if (code) next.set("insurer", code)
    else next.delete("insurer")
    setParams(next, { replace: true })
    // Remembered, because it is the same answer every time.
    if (code) remember(code)
  }

  const results = nearby.data?.results ?? []

  return (
    <div className="ml-shell py-6 pb-24 md:pb-10">
      <header className="max-w-prose">
        <h1 className="text-h1">{t("insurance_title")}</h1>
        <p className="mt-2 text-body text-ink-muted">
          {t("insurance_intro")}
        </p>
      </header>

      {/* Chips, not a select. There are a handful of insurers and the whole
          point of the page is to see which ones exist. */}
      <div
        role="group"
        aria-label={t("insurance_choose")}
        className="mt-5 flex flex-wrap gap-2"
      >
        {insurers.map((option) => {
          const active = option.code === selected
          return (
            <button
              key={option.code}
              type="button"
              aria-pressed={active}
              onClick={() => choose(active ? "" : option.code)}
              className={
                "ml-btn ml-btn-sm " +
                (active
                  ? "bg-primary text-white hover:bg-primary-hover"
                  : "border border-line-strong bg-surface text-ink hover:bg-surface-sunken")
              }
            >
              {option.name}
            </button>
          )
        })}
      </div>

      {!selected && (
        <div className="mt-6">
          <EmptyState
            title={t("insurance_pick_title")}
            body={t("insurance_pick_body")}
          />
        </div>
      )}

      {selected && (
        <section className="mt-8">
          <h2 className="text-h2">
            {t("insurance_accepting", { insurer: chosen?.name ?? selected })}
          </h2>
          {/* Says what the facility accepts. Never that this patient is
              covered - docs/11 section 7 rule 6. */}
          <p className="mt-1 max-w-prose text-small text-ink-muted">
            {t("insurance_disclaimer")}
          </p>

          {!hasOrigin && geo.status !== "locating" && (
            <div className="mt-4">
              <DistrictPicker
                message={t("location_denied")}
                selected={district}
                onPick={(picked) => {
                  const next = new URLSearchParams(params)
                  next.set("district", picked)
                  setParams(next, { replace: true })
                }}
                onRetry={locate}
              />
            </div>
          )}

          {nearby.isLoading && <ListSkeleton rows={3} />}

          {nearby.isError && (
            <div className="mt-4">
              <ErrorState
                title={t("error_generic")}
                action={
                  <Button size="sm" onClick={() => nearby.refetch()}>
                    {t("retry")}
                  </Button>
                }
              />
            </div>
          )}

          {hasOrigin && !nearby.isLoading && results.length === 0 && (
            <div className="mt-4">
              <Notice tone="info">
                {t("insurance_none_nearby", {
                  insurer: chosen?.name ?? selected,
                })}
              </Notice>
            </div>
          )}

          {results.length > 0 && (
            <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {results.map((facility) => (
                <FacilityCard
                  key={facility.id}
                  facility={facility}
                  insurerName={chosen?.name}
                />
              ))}
            </div>
          )}
        </section>
      )}
    </div>
  )
}
