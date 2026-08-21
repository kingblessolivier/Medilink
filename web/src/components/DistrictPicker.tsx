import { useI18n } from "../i18n"
import { useDistricts } from "../hooks/useNearbyFacilities"

/**
 * The fallback when geolocation is denied, unavailable, or out of bounds.
 * Never leave the patient with a blank screen.
 *
 * The district buttons used to render with no handler at all: they looked
 * interactive, and did nothing. That made this component the dead end it
 * exists to prevent, for exactly the patients least able to work around it -
 * anyone on a browser that will not hand over a location.
 */
export function DistrictPicker({
  message,
  selected,
  onPick,
  onRetry,
}: {
  message: string
  /** Highlights the district already being searched, if any. */
  selected?: string
  onPick: (district: string) => void
  onRetry: () => void
}) {
  const { t } = useI18n()
  const { data } = useDistricts()
  const districts = data?.results ?? []

  return (
    <div className="ml-card p-4">
      <p className="text-small text-ink">{message}</p>

      <p className="mt-3 text-small font-medium">{t("choose_district")}</p>

      {districts.length === 0 ? (
        // The list itself failed to load. Retrying the location is still a
        // way forward, so the button below is not the only thing on screen.
        <p className="mt-2 text-small text-ink-muted">
          {t("districts_unavailable")}
        </p>
      ) : (
        <div className="mt-2 flex flex-wrap gap-2" role="group">
          {districts.map((district) => {
            const active = selected === district
            return (
              <button
                key={district}
                type="button"
                aria-pressed={active}
                className={
                  active
                    ? "ml-btn-primary ml-btn-sm"
                    : "ml-btn-secondary ml-btn-sm"
                }
                onClick={() => onPick(district)}
              >
                {district}
              </button>
            )
          })}
        </div>
      )}

      <button className="ml-btn-secondary mt-4 w-full" onClick={onRetry}>
        {t("retry_location")}
      </button>
    </div>
  )
}
