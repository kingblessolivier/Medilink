import { useEffect } from "react"
import { Link } from "react-router-dom"
import { useI18n } from "../i18n"
import { useGeolocation } from "../hooks/useGeolocation"
import { useInsurers, useNearbyFacilities } from "../hooks/useNearbyFacilities"
import { useInsurerPreference } from "../hooks/useInsurerPreference"
import { useCurrentQueueEntry, useUpcomingAppointments } from "../hooks/useQueue"
import { usePatient } from "../hooks/useAuth"
import { FacilityCard } from "../components/FacilityCard"
import { InsurerChip } from "../components/InsurerChip"
import { LanguageToggle } from "../components/LanguageToggle"
import { DistrictPicker } from "../components/DistrictPicker"
import { QueueCard } from "../components/QueueCard"
import { AppointmentCard } from "../components/AppointmentCard"
import { Button, EmptyState, ErrorState, ListSkeleton, Notice } from "../ui"

/**
 * Home is state-dependent, and the state ordering is the product.
 *
 *   B  in a queue          -> the live card takes the whole screen
 *   C  appointment today   -> the appointment leads
 *   A  nothing active      -> discovery leads
 *
 * A patient who is already waiting must not have to scroll past a search box
 * to find out where they are in the queue.
 */
export function Home() {
  const { t } = useI18n()
  const { state: geo, locate } = useGeolocation()
  const { insurer, setInsurer } = useInsurerPreference()
  const { data: insurerData } = useInsurers()
  const patient = usePatient()

  // Both are patient-scoped, so they only run once somebody is signed in.
  const signedIn = patient !== null
  const queue = useCurrentQueueEntry(signedIn)
  const appointments = useUpcomingAppointments(signedIn)
  const nextAppointment = appointments.data?.[0] ?? null

  useEffect(() => {
    locate()
  }, [locate])

  const coords = geo.status === "ready" ? { lat: geo.lat, lng: geo.lng } : null
  const nearby = useNearbyFacilities(coords, { insurer })
  const insurerName = insurerData?.results.find((i) => i.code === insurer)?.name

  const geoFailed =
    geo.status === "denied" ||
    geo.status === "unavailable" ||
    geo.status === "out_of_bounds"

  return (
    <div className="mx-auto w-full max-w-2xl px-4 pb-24 pt-4">
      <header className="mb-5 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-h2">
            {patient?.full_name
              ? t("greeting_named", { name: patient.full_name })
              : t("greeting")}
          </h1>
          <p className="mt-0.5 text-small text-ink-muted">{t("tagline")}</p>
        </div>
        <LanguageToggle />
      </header>

      {/* --- State B: in a queue. Nothing competes with this. --- */}
      {queue.data && (
        <section className="mb-6" aria-label={t("your_queue")}>
          <QueueCard entry={queue.data} />
        </section>
      )}

      {/* --- State C: an appointment is coming up. --- */}
      {!queue.data && nextAppointment && (
        <section className="mb-6" aria-label={t("next_appointment")}>
          <AppointmentCard appointment={nextAppointment} />
        </section>
      )}

      {/* --- Discovery. Demoted, never removed. --- */}
      {!queue.data && (
        <section className="mb-6">
          <Link to="/search" className="ml-btn-primary w-full">
            {t("find_care")}
          </Link>
          <div className="mt-3">
            <InsurerChip insurer={insurer} onChange={setInsurer} />
          </div>
        </section>
      )}

      {geoFailed && (
        <div className="mb-6">
          <DistrictPicker
            message={
              geo.status === "out_of_bounds"
                ? t("out_of_bounds")
                : t("location_denied")
            }
            onRetry={locate}
          />
        </div>
      )}

      <section aria-labelledby="nearby-heading">
        <div className="mb-3 flex items-baseline justify-between">
          <h2 id="nearby-heading" className="ml-label">
            {t("nearby_open")}
          </h2>
          {nearby.data && nearby.data.count > 3 && (
            <Link to="/search" className="text-small font-medium text-primary">
              {t("see_all")}
            </Link>
          )}
        </div>

        {(geo.status === "locating" || nearby.isLoading) && <ListSkeleton rows={3} />}

        {nearby.isError && (
          <ErrorState
            title={t("error_generic")}
            action={
              <Button variant="secondary" size="sm" onClick={() => nearby.refetch()}>
                {t("retry")}
              </Button>
            }
          />
        )}

        {nearby.data?.query.radius_expanded && (
          <Notice tone="warning">
            {t("radius_expanded", {
              original: 5,
              actual: Math.round(nearby.data.query.radius / 1000),
            })}
          </Notice>
        )}

        {nearby.data?.results.length === 0 && (
          <EmptyState
            title={t("no_results")}
            body={t("no_results_body")}
            action={
              <Link to="/search" className="ml-btn-secondary ml-btn-sm">
                {t("change_filters")}
              </Link>
            }
          />
        )}

        <div className="mt-3 space-y-3">
          {nearby.data?.results.slice(0, 3).map((facility) => (
            <FacilityCard
              key={facility.id}
              facility={facility}
              insurerName={insurerName}
            />
          ))}
        </div>
      </section>
    </div>
  )
}
