import { useEffect } from "react"
import { Link, useNavigate } from "react-router-dom"
import { useI18n } from "../i18n"
import { useMediaQuery } from "../hooks/useMediaQuery"
import { useGeolocation } from "../hooks/useGeolocation"
import {
  useInsurers,
  useNearbyFacilities,
  useServiceTypes,
} from "../hooks/useNearbyFacilities"
import { useInsurerPreference } from "../hooks/useInsurerPreference"
import { useCurrentQueueEntry, useUpcomingAppointments } from "../hooks/useQueue"
import { usePatient } from "../hooks/useAuth"
import { useProviders } from "../hooks/useProviders"
import { useTriageStatus } from "../hooks/useTriageStatus"
import { FacilityCard } from "../components/FacilityCard"
import { NoLiveWaitNote } from "../components/NoLiveWaitNote"
import { DoctorCard } from "../components/DoctorCard"
import { GlobalSearch } from "../components/GlobalSearch"
import { HomeHeader } from "../components/HomeHeader"
import { DistrictPicker } from "../components/DistrictPicker"
import { CachedNotice } from "../components/CachedNotice"
import { QueueCard } from "../components/QueueCard"
import { AppointmentCard } from "../components/AppointmentCard"
import { Button, EmptyState, ErrorState, ListSkeleton, Notice } from "../ui"
import {
  IconChevronRight,
  IconShieldCheck,
  IconHeart,
  IconStethoscope,
} from "../ui/icons"

/* The three value points that used to sit in the hero are gone with it: the
   S-04 design puts quick actions there instead. The promise they carried -
   that a wait time is never guessed - is still made on /about, /help and by
   NoLiveWaitNote wherever a wait is actually missing, which is the place it
   lands hardest. */

/**
 * Home - healthcare discovery, and the state ordering IS the product.
 *
 *   B  in a queue         -> the live card takes the screen; nothing competes
 *   C  appointment today  -> the appointment leads
 *   A  nothing active     -> discovery leads
 *
 * A patient already waiting must not scroll past a search box to find out
 * where they are in the queue.
 */
export function Home() {
  const { t, lang } = useI18n()
  const navigate = useNavigate()
  const { state: geo, locate } = useGeolocation()
  const { insurer } = useInsurerPreference()
  const patient = usePatient()

  const signedIn = patient !== null
  const queue = useCurrentQueueEntry(signedIn)
  const appointments = useUpcomingAppointments(signedIn)
  const nextAppointment = appointments.data?.[0] ?? null

  useEffect(() => {
    locate()
  }, [locate])

  const coords = geo.status === "ready" ? { lat: geo.lat, lng: geo.lng } : null
  const nearby = useNearbyFacilities(coords, { insurer })
  const doctors = useProviders({ limit: 4 })
  const { data: serviceData } = useServiceTypes()
  const { data: insurerData } = useInsurers()
  const triage = useTriageStatus()

  const insurerName = insurerData?.results.find((i) => i.code === insurer)?.name

  /* The header chip names the insurer the PATIENT has saved on their record,
     falling back to the local browser preference for somebody signed out.
     Those are two different things and the header wants the first: a signed-in
     patient who set their insurer on another device should still see it here,
     and `useInsurerPreference` only ever knows about this browser.

     It names the insurer and stops. Not "active", not "covered" - MediLink
     knows which insurer was chosen, never whether the membership is paid up. */
  const headerInsurerName =
    insurerData?.results.find(
      (i) => i.code === (patient?.insurer ?? insurer),
    )?.name ?? null
  // Three on a phone, six once the grid has columns to fill. Home is a
  // summary; the full list is one tap away and always was.
  const wide = useMediaQuery("(min-width: 768px)")
  const nearbyLimit = wide ? 6 : 3
  const busy = geo.status === "locating" || nearby.isLoading
  const geoFailed =
    geo.status === "denied" ||
    geo.status === "unavailable" ||
    geo.status === "out_of_bounds"

  const serviceLabel = (s: { name_rw: string; name_en: string; name_fr: string }) =>
    lang === "rw" ? s.name_rw : lang === "fr" ? s.name_fr : s.name_en

  return (
    <div className="pb-24 md:pb-10">
      {/* ---- States B and C sit ABOVE the hero and outside it.
             A patient already in a queue must not scroll past a search box
             to find out what number they are. ---- */}
      {(queue.data || nextAppointment) && (
        <div className="ml-shell pt-4">
          {queue.data ? (
            <section aria-label={t("your_queue")}>
              <QueueCard entry={queue.data} />
            </section>
          ) : (
            <section aria-label={t("next_appointment")}>
              <AppointmentCard appointment={nextAppointment!} />
            </section>
          )}
        </div>
      )}

      {/* ---- Hero. Demoted to a strip when something is active, never
             removed: discovery is still the product. ---- */}
      {!queue.data && (
        <HomeHeader
          name={patient?.full_name ?? null}
          insurerName={headerInsurerName}
          hasActiveAppointment={Boolean(nextAppointment)}
        >
          <GlobalSearch coords={coords} />
        </HomeHeader>
      )}

      <div className="ml-shell pt-8">
        {/* The insurer card that used to sit here is gone. S-04 puts the
            insurer in the header chip instead, and keeping both meant two
            controls disagreeing on screen: the chip reads the patient record,
            the card read this browser localStorage, so a patient whose
            insurer was saved server-side saw "Mutuelle de Sante" above "no
            insurance set". Changing it still lives on /insurance, which is a
            primary tab, and on the profile. */}
        {geoFailed && (
          <div className="mb-6 max-w-2xl">
            {/* Home is a summary. Picking a district hands off to /search,
                where the filters and the full list already live, rather than
                growing a second half-featured results list here. */}
            <DistrictPicker
              message={
                geo.status === "out_of_bounds"
                  ? t("out_of_bounds")
                  : t("location_denied")
              }
              onPick={(district) =>
                navigate(`/search?district=${encodeURIComponent(district)}`)
              }
              onRetry={locate}
            />
          </div>
        )}

        {/* ---- Nearby ---- */}
        <Section
          title={t("nearby_open")}
          action={
            nearby.data && nearby.data.count > 3 ? (
              // `inline-flex min-h-touch` rather than bare text: this is a
              // standalone navigation control, not a link inside a sentence,
              // so rule 6 applies to it. It measured 22px.
              <Link
                to="/search"
                className="inline-flex min-h-touch items-center text-body font-medium text-primary"
              >
                {t("see_all")}
              </Link>
            ) : null
          }
        >
          {busy && <ListSkeleton rows={3} />}

          {/* The fourth state, and the one that was missing.
              With no coordinates the query is DISABLED, so it is not loading,
              not errored and has no data - every branch below is false and the
              section rendered as a heading over nothing. That is the default
              experience for anyone who declines the location prompt, which on
              a health site is a lot of people. Say what is needed instead. */}
          {!coords && !busy && (
            <EmptyState
              title={t("nearby_needs_a_place_title")}
              body={t("nearby_needs_a_place_body")}
            />
          )}

          {nearby.isError && (
            <ErrorState
              title={t("error_generic")}
              action={
                <Button size="sm" onClick={() => nearby.refetch()}>
                  {t("retry")}
                </Button>
              }
            />
          )}

          <div className="mb-3 empty:mb-0">
            <CachedNotice updatedAt={nearby.dataUpdatedAt} />
          </div>

          {nearby.data?.query.radius_expanded && (
            <div className="mb-3">
              <Notice tone="warning">
                {t("radius_expanded", {
                  original: 5,
                  actual: Math.round(nearby.data.query.radius / 1000),
                })}
              </Notice>
            </div>
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

          {/* A grid, not a stack. Three full-width cards on a 1440px monitor
              was a column of 1100px-wide boxes with one line of text in each. */}
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {nearby.data?.results.slice(0, nearbyLimit).map((facility) => (
              <FacilityCard
                key={facility.id}
                facility={facility}
                insurerName={insurerName}
              />
            ))}
          </div>
          <NoLiveWaitNote
            facilities={nearby.data?.results.slice(0, nearbyLimit) ?? []}
            className="mt-3"
          />
        </Section>

        {/* ---- Doctors. Omitted entirely when none are listed, rather than
               showing an empty shelf. ---- */}
        {(doctors.data?.count ?? 0) > 0 && (
          <Section
            title={t("doctors_near_you")}
            action={
              <Link
                to="/doctors"
                className="inline-flex min-h-touch items-center text-body font-medium text-primary"
              >
                {t("see_all")}
              </Link>
            }
          >
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {/* Three, to fill the row exactly. The API returns four, which
                  left one card stranded on a second row under two columns of
                  whitespace - the "See all" link is the route to the rest. */}
              {doctors.data?.results.slice(0, 3).map((doctor) => (
                <DoctorCard key={doctor.slug} doctor={doctor} />
              ))}
            </div>
          </Section>
        )}

        {/* ---- Services. A list of links, not a wall of cards. ---- */}
        {/* Services were eight identical grey pills - indistinguishable, and
            impossible to scan for the one you came for. Now a tile each, with
            the same icon plate the rest of the product uses as an anchor. */}
        <Section title={t("popular_services")}>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {(serviceData?.results ?? []).slice(0, 8).map((service) => (
              <Link
                key={service.code}
                to={`/search?service=${service.code}`}
                className="ml-card-interactive group flex items-center gap-3 p-3.5"
              >
                <span className="ml-icon-plate bg-primary-light text-primary">
                  <IconStethoscope size={18} />
                </span>
                <span className="min-w-0 flex-1 truncate text-body-lg font-medium">
                  {serviceLabel(service)}
                </span>
                <IconChevronRight
                  size={16}
                  className="shrink-0 text-n600 transition-transform group-hover:translate-x-0.5"
                />
              </Link>
            ))}
          </div>
        </Section>

        {/* ---- Insurance ---- */}
        <Section title={t("insurance_title")}>
          <div className="ml-panel overflow-hidden">
            <div className="flex flex-col gap-6 p-5 sm:flex-row sm:items-start sm:p-6">
              <span className="ml-icon-plate h-11 w-11 bg-primary-light text-primary">
                <IconShieldCheck size={22} />
              </span>
              <div className="min-w-0 flex-1">
                <p className="max-w-prose text-body-lg text-n700">
                  {t("insurance_body")}
                </p>
                <div className="mt-4 flex flex-wrap gap-2">
                  {(insurerData?.results ?? []).slice(0, 8).map((option) => (
                    <Link
                      key={option.code}
                      to={`/search?insurer=${option.code}`}
                      className="ml-btn-secondary ml-btn-sm"
                    >
                      {option.name}
                    </Link>
                  ))}
                </div>
                {/* Rule 6, on the screen rather than only in the docs: we say
                    what a facility ACCEPTS, never that a patient is covered. */}
                <p className="mt-4 text-label text-n600">
                  {t("insurance_accepts_note")}
                </p>
              </div>
            </div>
          </div>
        </Section>

        {/* ---- Care Guide. Present only when a clinician has signed off. ---- */}
        {triage.available && (
          <Section title={t("care_guide_title")}>
            <div className="ml-panel flex flex-col gap-6 p-5 sm:flex-row sm:items-start sm:p-6">
              <span className="ml-icon-plate h-11 w-11 bg-primary-light text-primary">
                <IconHeart size={22} />
              </span>
              <div className="min-w-0 flex-1">
                <p className="max-w-prose text-body-lg text-n700">
                  {t("care_guide_body")}
                </p>
                <Link to="/care-guide" className="ml-btn-primary mt-4">
                  {t("start_care_guide")}
                </Link>
                <p className="mt-3 text-label text-n600">
                  {t("care_guide_disclaimer")}
                </p>
              </div>
            </div>
          </Section>
        )}
      </div>
    </div>
  )
}

/** A titled section. A divider and whitespace, not another card. */
function Section({
  title,
  action,
  children,
}: {
  title: string
  action?: React.ReactNode
  children: React.ReactNode
}) {
  return (
    <section className="ml-section">
      {/* Was a 12px grey uppercase label that read as a form field caption.
          A section heading on a page this wide has to hold its own column. */}
      <div className="ml-section-head">
        <h2 className="text-h2">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  )
}
