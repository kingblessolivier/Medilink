import { Link, useParams } from "react-router-dom"
import { IconHospital } from "../ui/icons"
import { useEffect } from "react"
import { useI18n } from "../i18n"
import { useGeolocation } from "../hooks/useGeolocation"
import { useNearbyFacilities, useServiceTypes } from "../hooks/useNearbyFacilities"
import { useInsurerPreference } from "../hooks/useInsurerPreference"
import { useInsurers } from "../hooks/useNearbyFacilities"
import { useProviders } from "../hooks/useProviders"
import { useSpecialties } from "../hooks/useSpecialties"
import { FacilityCard } from "../components/FacilityCard"
import { DoctorCard } from "../components/DoctorCard"
import { EmptyState, ErrorState, ListSkeleton, Notice } from "../ui"

/**
 * One service, and everywhere it can be had.
 *
 * This is the page a search result or a Care Guide recommendation lands on,
 * so it has to close the loop rather than describe: which facilities offer it
 * near me, which doctors deliver it, and does my insurance cover it.
 *
 * Composed entirely from endpoints that already exist - a service is a lens on
 * the directory rather than a thing with its own record.
 */
export function ServiceDetail() {
  const { code = "" } = useParams()
  const { t, lang } = useI18n()
  const { state: geo, locate } = useGeolocation()
  const { insurer } = useInsurerPreference()

  useEffect(() => {
    locate()
  }, [locate])

  const coords = geo.status === "ready" ? { lat: geo.lat, lng: geo.lng } : null
  const facilities = useNearbyFacilities(coords, { service: code, insurer })
  const doctors = useProviders({ service: code, limit: 6 })
  const { data: serviceData } = useServiceTypes()
  const { data: specialtyData } = useSpecialties()
  const { data: insurerData } = useInsurers()

  const service = serviceData?.results.find((s) => s.code === code)
  const insurerName = insurerData?.results.find((i) => i.code === insurer)?.name

  const name = service
    ? lang === "rw"
      ? service.name_rw
      : lang === "fr"
        ? service.name_fr
        : service.name_en
    : code.replace(/_/g, " ")

  // Which specialties deliver this service - the reverse of the Care Guide
  // mapping, and how a patient learns what kind of clinician to expect.
  const specialties = (specialtyData?.results ?? []).filter((s) =>
    s.service_types.includes(code),
  )

  const results = facilities.data?.results ?? []

  return (
    <div className="ml-page py-6 pb-24">
      <Link to="/search" className="text-small font-medium text-primary">
        {t("back")}
      </Link>

      <h1 className="mt-2 text-h1">{name}</h1>

      {specialties.length > 0 && (
        <p className="mt-1.5 max-w-prose text-body text-ink-muted">
          {t("service_delivered_by", {
            specialties: specialties
              .map((s) =>
                lang === "rw" ? s.name_rw : lang === "fr" ? s.name_fr : s.name_en,
              )
              .join(", "),
          })}
        </p>
      )}

      <div className="mt-4 flex flex-wrap gap-2">
        <Link to={`/search?service=${code}`} className="ml-btn-primary">
          {t("find_care")}
        </Link>
        <Link to={`/doctors?specialty=${specialties[0]?.code ?? ""}`}
              className="ml-btn-secondary">
          {t("tab_doctors")}
        </Link>
      </div>

      {/* ------------------------------------------------------ facilities */}
      <section className="ml-section">
        <div className="mb-3 flex items-baseline justify-between">
          <h2 className="text-h3">{t("where_to_get_it")}</h2>
          {results.length > 3 && (
            <Link
              to={`/search?service=${code}`}
              className="text-small font-medium text-primary"
            >
              {t("see_all")}
            </Link>
          )}
        </div>

        {(geo.status === "locating" || facilities.isLoading) && (
          <ListSkeleton rows={3} />
        )}

        {facilities.isError && (
          <ErrorState
            title={t("error_generic")}
            action={
              <button
                className="ml-btn-secondary ml-btn-sm"
                onClick={() => facilities.refetch()}
              >
                {t("retry")}
              </button>
            }
          />
        )}

        {facilities.data?.query.radius_expanded && (
          <div className="mb-3">
            <Notice tone="warning">
              {t("radius_expanded", {
                original: 5,
                actual: Math.round(facilities.data.query.radius / 1000),
              })}
            </Notice>
          </div>
        )}

        {facilities.data && results.length === 0 && (
          <EmptyState icon={<IconHospital size={20} />}
            title={t("no_facilities_for_service", { service: name })}
            body={t("no_results_body")}
            action={
              <Link to="/search" className="ml-btn-secondary ml-btn-sm">
                {t("find_care")}
              </Link>
            }
          />
        )}

        <div className="space-y-3">
          {results.slice(0, 3).map((facility) => (
            <FacilityCard
              key={facility.id}
              facility={facility}
              insurerName={insurerName}
            />
          ))}
        </div>
      </section>

      {/* --------------------------------------------------------- doctors */}
      {(doctors.data?.count ?? 0) > 0 && (
        <section className="ml-section">
          <h2 className="text-h3 mb-3">{t("who_provides_it")}</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            {doctors.data?.results.map((doctor) => (
              <DoctorCard key={doctor.slug} doctor={doctor} />
            ))}
          </div>
        </section>
      )}

      {/* ------------------------------------------------------- insurance */}
      <section className="ml-section">
        <h2 className="text-h3 mb-2">{t("tab_insurance")}</h2>
        <Notice tone="info">{t("service_insurance_note")}</Notice>
      </section>
    </div>
  )
}
