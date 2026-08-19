import { useEffect } from "react"
import { Link } from "react-router-dom"
import { useQueryClient } from "@tanstack/react-query"
import { api } from "../api/client"
import { useI18n } from "../i18n"
import { useAuth } from "../hooks/useAuth"
import { useGeolocation } from "../hooks/useGeolocation"
import { useInsurers, useNearbyFacilities } from "../hooks/useNearbyFacilities"
import { useInsurerPreference } from "../hooks/useInsurerPreference"
import { useCurrentQueueEntry, useUpcomingAppointments } from "../hooks/useQueue"
import { FacilityCard } from "../components/FacilityCard"
import { InsurerChip } from "../components/InsurerChip"
import { LanguageToggle } from "../components/LanguageToggle"
import { DistrictPicker } from "../components/DistrictPicker"
import { QueueCard } from "../components/QueueCard"
import { AppointmentCard } from "../components/AppointmentCard"

/**
 * The home screen answers one question: where do I go, and when should I leave?
 *
 * It is state-dependent:
 *   A  nothing active        -> search hero + nearby list
 *   B  in a queue            -> live queue card REPLACES the hero
 *   C  appointment today     -> appointment card above the hero
 *
 * State B wins over C: if you are already checked in, the queue is the only
 * thing that matters.
 */
export function Home() {
  const { t } = useI18n()
  const { session } = useAuth()
  const queryClient = useQueryClient()
  const { state: geo, locate } = useGeolocation()
  const { insurer, setInsurer } = useInsurerPreference()
  const { data: insurerData } = useInsurers()

  const signedIn = session.state === "signed_in"
  const queue = useCurrentQueueEntry(signedIn)
  const appointments = useUpcomingAppointments(signedIn)

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

  const activeEntry = queue.data ?? null
  const todaysAppointment = (appointments.data ?? []).find(
    (a) => new Date(a.slot_start).toDateString() === new Date().toDateString(),
  )

  async function cancelAppointment(id: number) {
    await api.cancelAppointment(id)
    await queryClient.invalidateQueries({ queryKey: ["appointments"] })
  }

  return (
    <div className="mx-auto max-w-md px-4 pb-24 pt-4">
      <header className="mb-4 flex items-start justify-between gap-2">
        <div>
          <p className="text-lg font-semibold">
            {session.state === "signed_in" && session.patient.full_name
              ? t("greeting_named", { name: session.patient.full_name })
              : t("greeting")}
          </p>
        </div>
        <LanguageToggle />
      </header>

      {/* State B: the live queue card replaces the search hero entirely. */}
      {activeEntry ? (
        <QueueCard entry={activeEntry} />
      ) : (
        <>
          {/* State C sits above the hero - it is information, not the task. */}
          {todaysAppointment && (
            <AppointmentCard
              appointment={todaysAppointment}
              onCancel={() => cancelAppointment(todaysAppointment.id)}
            />
          )}

          <Link to="/search" className="btn-primary mb-3 w-full">
            {t("find_care")}
          </Link>

          <div className="mb-5">
            <InsurerChip insurer={insurer} onChange={setInsurer} />
          </div>
        </>
      )}

      {!signedIn && (
        <Link
          to="/sign-in"
          className="mb-5 block rounded-xl border border-dashed border-neutral-300 p-3 text-center text-sm text-primary"
        >
          {t("auth_prompt")}
        </Link>
      )}

      {!activeEntry && (
        <>
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

          {(geo.status === "locating" || nearby.isLoading) && (
            <p className="text-sm text-neutral-500">{t("loading")}</p>
          )}

          {nearby.isError && (
            <div className="card">
              <p className="text-sm text-danger">{t("error_generic")}</p>
              <button
                className="btn-secondary mt-3 w-full"
                onClick={() => nearby.refetch()}
              >
                {t("retry")}
              </button>
            </div>
          )}

          {nearby.data && (
            <section>
              <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-neutral-500">
                {t("nearby_open")}
              </h2>

              {nearby.data.query.radius_expanded && (
                <p className="mb-3 rounded-lg bg-amber-50 p-3 text-sm text-warning">
                  {t("radius_expanded", {
                    original: 5,
                    actual: Math.round(nearby.data.query.radius / 1000),
                  })}
                </p>
              )}

              {nearby.data.results.length === 0 && (
                <p className="text-sm text-neutral-500">{t("no_results")}</p>
              )}

              {nearby.data.results.slice(0, 3).map((facility) => (
                <FacilityCard
                  key={facility.id}
                  facility={facility}
                  insurerName={insurerName}
                />
              ))}

              {nearby.data.results.length > 3 && (
                <Link
                  to="/search"
                  className="block py-2 text-center text-sm text-primary"
                >
                  {t("see_all")}
                </Link>
              )}
            </section>
          )}
        </>
      )}
    </div>
  )
}
