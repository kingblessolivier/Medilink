import { useEffect, useState } from "react"
import { useI18n } from "../i18n"
import { useGeolocation } from "../hooks/useGeolocation"
import {
  useInsurers,
  useNearbyFacilities,
  useServiceTypes,
} from "../hooks/useNearbyFacilities"
import { useInsurerPreference } from "../hooks/useInsurerPreference"
import { FacilityCard } from "../components/FacilityCard"
import { DistrictPicker } from "../components/DistrictPicker"

type ServiceLabels = { name_rw: string; name_en: string; name_fr: string }

export function Search() {
  const { t, lang } = useI18n()
  const { state: geo, locate } = useGeolocation()
  const { insurer, setInsurer } = useInsurerPreference()
  const [service, setService] = useState<string | undefined>()
  const [openNow, setOpenNow] = useState(false)

  useEffect(() => {
    locate()
  }, [locate])

  const coords = geo.status === "ready" ? { lat: geo.lat, lng: geo.lng } : null
  const query = useNearbyFacilities(coords, { insurer, service, openNow })
  const { data: insurerData } = useInsurers()
  const { data: serviceData } = useServiceTypes()
  const insurerName = insurerData?.results.find((i) => i.code === insurer)?.name

  const serviceLabel = (s: ServiceLabels) =>
    lang === "rw" ? s.name_rw : lang === "fr" ? s.name_fr : s.name_en

  const geoFailed =
    geo.status === "denied" ||
    geo.status === "unavailable" ||
    geo.status === "out_of_bounds"

  return (
    <div className="mx-auto max-w-md px-4 pb-24 pt-4">
      <div className="card mb-4 space-y-3">
        <label className="block">
          <span className="text-sm text-neutral-600">{t("filter_service")}</span>
          <select
            className="mt-1 min-h-touch w-full rounded-lg border border-neutral-300 px-2"
            value={service ?? ""}
            onChange={(e) => setService(e.target.value || undefined)}
          >
            <option value="">{t("all_services")}</option>
            {(serviceData?.results ?? []).map((s) => (
              <option key={s.code} value={s.code}>
                {serviceLabel(s)}
              </option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className="text-sm text-neutral-600">{t("filter_insurer")}</span>
          <select
            className="mt-1 min-h-touch w-full rounded-lg border border-neutral-300 px-2"
            value={insurer ?? ""}
            onChange={(e) => setInsurer(e.target.value || undefined)}
          >
            <option value="">{t("no_cover_set")}</option>
            {(insurerData?.results ?? []).map((i) => (
              <option key={i.code} value={i.code}>
                {i.name}
              </option>
            ))}
          </select>
        </label>

        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            className="h-5 w-5"
            checked={openNow}
            onChange={(e) => setOpenNow(e.target.checked)}
          />
          <span className="text-sm">{t("filter_open_now")}</span>
        </label>
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

      {query.isLoading && (
        <p className="text-sm text-neutral-500">{t("loading")}</p>
      )}

      {query.data?.results.length === 0 && (
        <p className="text-sm text-neutral-500">{t("no_results")}</p>
      )}

      {query.data?.results.map((facility) => (
        <FacilityCard
          key={facility.id}
          facility={facility}
          insurerName={insurerName}
        />
      ))}
    </div>
  )
}
