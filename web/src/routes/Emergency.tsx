/**
 * S-13, the emergency screen, per docs/01_patient_app.html: call 912, and the
 * nearest accident and emergency.
 *
 * THE PHONE NUMBER COMES FIRST AND ALWAYS RENDERS. It is above the list, it
 * does not wait for geolocation, it does not wait for the network, and it is
 * not behind a query that can fail. Every other screen in this product can
 * afford to be empty while something loads. This one cannot: somebody opening
 * it is having the worst moment this app will ever be present for, and the
 * single most useful thing MediLink can do is put 912 under their thumb before
 * anything else has resolved.
 *
 * "NEAREST A&E" IS ANSWERED HONESTLY OR NOT AT ALL. The list is facilities
 * that declare the `emergency` service themselves - not the nearest hospital,
 * and not an inference from `level`. A district hospital without an emergency
 * department is not an answer to this question, and sending somebody bleeding
 * to the wrong gate is worse than sending them nowhere. When the filter
 * returns nothing, the screen says so and repeats the number.
 */

import { useEffect } from "react"
import { Link } from "react-router-dom"
import { useI18n } from "../i18n"
import { useGeolocation } from "../hooks/useGeolocation"
import { useNearbyFacilities } from "../hooks/useNearbyFacilities"
import { ListSkeleton } from "../ui"
import { IconPhone, IconPin } from "../ui/icons"

/** One string, one place - it is on posters and in the footer. */
const EMERGENCY_NUMBER = "912"

export function Emergency() {
  const { t } = useI18n()
  const { state: geo, locate } = useGeolocation()
  const coords = geo.status === "ready" ? { lat: geo.lat, lng: geo.lng } : null
  const nearby = useNearbyFacilities(coords, { service: "emergency" })

  /* Asked for on mount rather than behind a button. Every other screen waits
     for a tap before reaching for location, because a permission prompt on
     arrival is rude. This one is the exception: the whole value of the list
     is that it is sorted by how far away it is, and somebody who opens this
     screen has no attention to spend on a second tap. */
  useEffect(() => {
    if (geo.status === "idle") locate()
  }, [geo.status, locate])

  /* Re-sorted by distance, and only on this screen.
   *
   * /facilities/nearby ranks by `tier` before distance - open facilities
   * ahead of closed ones - which is right everywhere else: an open clinic
   * that takes your insurance beats a closer shut one. It is wrong here for
   * two reasons. An accident and emergency department runs through the night
   * while the facility's listed outpatient hours say closed, so `is_open` is
   * not a fact about the service this screen is filtering for. And a list
   * headed "nearest emergency care" that reads 0.4 km, 3.8 km, 1.0 km looks
   * broken to somebody who is frightened.
   *
   * Facilities with no distance - a district search, no coordinates - sort
   * last rather than first, which is where an unknown belongs.
   */
  const facilities = [...(nearby.data?.results ?? [])].sort(
    (a, b) =>
      (a.distance_m ?? Number.POSITIVE_INFINITY) -
      (b.distance_m ?? Number.POSITIVE_INFINITY),
  )

  return (
    <div className="mx-auto w-full max-w-xl px-4 py-6 pb-24 md:pb-10">
      <h1 className="text-h1 text-n900">{t("emergency_title")}</h1>
      <p className="mt-2 text-body-lg text-n700">{t("emergency_body")}</p>

      {/* Not a Button component: this is an <a href="tel:">, it is the only
          thing on the screen that matters, and it is deliberately the largest
          touch target in the product. */}
      <a
        href={`tel:${EMERGENCY_NUMBER}`}
        className="mt-5 flex min-h-[64px] w-full items-center justify-center gap-3 rounded-pill bg-danger px-6 text-h2 font-bold text-white active:scale-[0.97]"
      >
        <IconPhone size={24} />
        {t("emergency_call_now", { number: EMERGENCY_NUMBER })}
      </a>

      <h2 className="mt-8 text-h3 text-n900">{t("emergency_nearest")}</h2>

      {nearby.isLoading && (
        <div className="mt-3">
          <ListSkeleton rows={2} />
        </div>
      )}

      {/* An error here is not worth its own panel. The number above already
          works, and a red error box under a red call button would compete
          with the one thing this screen is for. */}
      {!nearby.isLoading && facilities.length === 0 && (
        <p className="mt-3 text-body-lg text-n700">
          {t("emergency_none", { number: EMERGENCY_NUMBER })}
        </p>
      )}

      <ul className="mt-3 space-y-3">
        {facilities.map((facility) => (
          <li
            key={facility.slug}
            className="rounded-lg border border-n200 bg-white p-4"
          >
            <Link
              to={`/facility/${facility.slug}`}
              className="text-body-lg font-medium text-n900 hover:text-primary"
            >
              {facility.name}
            </Link>
            <p className="mt-1 flex items-center gap-1.5 text-body text-n600">
              <IconPin size={14} />
              {facility.distance_m !== null && facility.distance_m !== undefined
                ? `${(facility.distance_m / 1000).toFixed(1)} km`
                : facility.district}
            </p>

            <div className="mt-3 flex flex-wrap gap-2">
              <a
                className="ml-btn-primary ml-btn-sm"
                href={`https://www.google.com/maps/dir/?api=1&destination=${facility.location.lat},${facility.location.lng}`}
                target="_blank"
                rel="noreferrer"
              >
                {t("directions")}
              </a>
              {/* Only when the facility actually gave us a number. */}
              {facility.phone && (
                <a className="ml-btn-secondary ml-btn-sm" href={`tel:${facility.phone}`}>
                  {facility.phone}
                </a>
              )}
            </div>
          </li>
        ))}
      </ul>

      <p className="mt-6 text-body text-n600">
        {t("emergency_disclaimer", { number: EMERGENCY_NUMBER })}
      </p>
    </div>
  )
}

export default Emergency
