import { useI18n } from "../i18n"
import { useDistricts } from "../hooks/useNearbyFacilities"

/**
 * The fallback when geolocation is denied, unavailable, or out of bounds.
 * Never leave the patient with a blank screen.
 */
export function DistrictPicker({
  message,
  onRetry,
}: {
  message: string
  onRetry: () => void
}) {
  const { t } = useI18n()
  const { data } = useDistricts()

  return (
    <div className="card">
      <p className="text-sm text-neutral-700">{message}</p>
      <p className="mt-3 text-sm font-medium">{t("choose_district")}</p>
      <div className="mt-2 flex flex-wrap gap-2">
        {(data?.results ?? []).map((district) => (
          <button key={district} className="btn-secondary text-sm">
            {district}
          </button>
        ))}
      </div>
      <button className="btn-primary mt-4 w-full" onClick={onRetry}>
        {t("retry")}
      </button>
    </div>
  )
}
