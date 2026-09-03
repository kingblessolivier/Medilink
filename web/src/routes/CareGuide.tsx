import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { useMutation, useQuery } from "@tanstack/react-query"
import { api } from "../api/client"
import { useI18n } from "../i18n"
import { useTriageStatus } from "../hooks/useTriageStatus"
import { useGeolocation } from "../hooks/useGeolocation"
import { useNearbyFacilities } from "../hooks/useNearbyFacilities"
import type { Translation, TriageCheck } from "../api/types"
import { Badge, Card, ListSkeleton, Notice } from "../ui"
import { IconClock, IconPhone, IconPin, IconStethoscope } from "../ui/icons"

/**
 * The Care Guide. One box, one answer.
 *
 * A patient types how they feel and gets back what it might be, where to go,
 * who works there, which insurers are accepted, and how long the queue is. No
 * questionnaire, no account, no sign-in - somebody who is unwell should not
 * have to register before finding out where to go.
 *
 * It replaced a four-step flow: a landing card, a text box, a menu of
 * clinician-authored questions, then a result. The questions were the rigorous
 * way to narrow things down, and they were also four screens between a sick
 * person and an answer.
 *
 * THREE THINGS SURVIVED THE SIMPLIFICATION, each load-bearing:
 *
 * 1. RED-FLAG SCREENING. The old flow asked every red-flag question before
 *    anything else, so no phrase could route a patient past it. With the
 *    questions gone that guarantee moved into the phrase list: an entry can be
 *    marked `red_flag`, and one match escalates on its own - emergency
 *    guidance, no conditions, and no clinic offered as an alternative.
 * 2. THE DISCLAIMER, on every response, in the patient's language, written by
 *    the clinician who signed the protocol and never paraphrased here.
 * 3. THE GATE. `/triage/status` still decides whether any of this is
 *    reachable, and it stays shut until a named clinician signs a protocol.
 *
 * The condition list is not a diagnosis, and the wording carries that: "what
 * your answers point to", and a share of what matched rather than a
 * probability. The service to attend still comes from the signed protocol.
 */
export function CareGuide() {
  const { t, lang } = useI18n()
  const status = useTriageStatus()
  const { state: geo, locate } = useGeolocation()
  const coords = geo.status === "ready" ? { lat: geo.lat, lng: geo.lng } : null

  /* Asked for on arrival rather than behind a tap.
   *
     Without it `geo.status` stays "idle", coords stay null, and the "where to
     go" section renders nothing at all - the answer stops at the condition
     list, which is half the thing that was asked for. The Emergency screen
     makes the same call for the same reason: the whole value of the facility
     list is that it is ordered by how far away it is, and somebody who is
     unwell has no attention to spend on a second tap. A patient who refuses
     the prompt still gets the conditions and the disclaimer. */
  useEffect(() => {
    if (geo.status === "idle") locate()
  }, [geo.status, locate])

  const [text, setText] = useState("")
  const [result, setResult] = useState<TriageCheck | null>(null)

  const check = useMutation({
    mutationFn: () => api.triageCheck(text),
    onSuccess: setResult,
  })

  const say = (value: Translation | null | undefined) =>
    value ? (value[lang] ?? value.en) : ""

  if (status.isLoading) {
    return (
      <div className="ml-page py-6">
        <ListSkeleton rows={1} />
      </div>
    )
  }

  // The gate. Honest about why, rather than a broken flow or a spinner.
  if (!status.available) {
    return (
      <div className="mx-auto w-full max-w-xl px-4 py-6 pb-24 md:pb-10">
        <h1 className="text-h1">{t("care_guide")}</h1>
        <div className="mt-4">
          <Notice tone="info">{t("care_guide_unavailable")}</Notice>
        </div>
        <p className="mt-4 text-body-lg text-n700">
          {t("care_guide_unavailable_body")}
        </p>
        <div className="mt-6 flex flex-wrap gap-2">
          <Link to="/search" className="ml-btn-primary">
            {t("find_care")}
          </Link>
          <Link to="/doctors" className="ml-btn-secondary">
            {t("nav_doctors")}
          </Link>
        </div>
      </div>
    )
  }

  // A red flag ends everything. The only useful things now are the number and
  // the nearest emergency department - not a list to weigh up.
  if (result?.escalate_emergency) {
    return (
      <div className="mx-auto w-full max-w-xl px-4 py-6 pb-24 md:pb-10">
        <h1 className="text-h1 text-danger">
          {t("care_guide_emergency_label")}
        </h1>
        <p className="mt-3 text-body-lg text-n900">
          {say(result.emergency_advice)}
        </p>
        <a
          href={`tel:${t("emergency_number")}`}
          className="mt-5 flex min-h-[64px] items-center justify-center gap-3 rounded-pill bg-danger px-6 text-h2 font-bold text-white"
        >
          <IconPhone size={24} />
          {t("care_guide_call_912", { number: t("emergency_number") })}
        </a>
        <Link to="/emergency" className="ml-btn-secondary mt-3 w-full">
          {t("emergency_nearest")}
        </Link>
        <Disclaimer text={say(result.disclaimer)} />
      </div>
    )
  }

  return (
    <div className="mx-auto w-full max-w-xl px-4 py-6 pb-24 md:pb-10">
      <h1 className="text-h1">{t("care_guide")}</h1>

      <label htmlFor="feeling" className="mt-5 block text-body-lg font-medium">
        {t("cg_prompt")}
      </label>
      <textarea
        id="feeling"
        rows={3}
        maxLength={300}
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={t("cg_placeholder")}
        className="mt-2 w-full rounded-lg border border-n300 bg-white px-4 py-3 text-body-lg placeholder:text-n600 focus-visible:border-primary focus-visible:outline-none"
      />
      <button
        className="ml-btn-primary mt-3 w-full"
        disabled={text.trim().length < 3 || check.isPending}
        onClick={() => check.mutate()}
      >
        {t("cg_submit")}
      </button>

      {check.isPending && (
        <div className="mt-6">
          <ListSkeleton rows={2} />
        </div>
      )}

      {result && !check.isPending && (
        <Answer result={result} coords={coords} say={say} />
      )}
    </div>
  )
}

/** What it might be, then where to go. In that order. */
function Answer({
  result,
  coords,
  say,
}: {
  result: TriageCheck
  coords: { lat: number; lng: number } | null
  say: (v: Translation | null | undefined) => string
}) {
  const { t, lang } = useI18n()

  // Nothing recognised. Saying so beats an empty result, which reads as
  // reassurance - "we found nothing wrong" is not what happened.
  if (!result.matched || result.conditions.length === 0) {
    return (
      <div className="mt-6">
        <Notice tone="warning">{t("cg_no_match")}</Notice>
        <Link to="/search" className="ml-btn-secondary mt-3 w-full">
          {t("find_care")}
        </Link>
        <Disclaimer text={say(result.disclaimer)} />
      </div>
    )
  }

  return (
    <div className="mt-6">
      <h2 className="text-h3">{t("care_guide_conditions_title")}</h2>
      <p className="mt-1 text-body text-n700">
        {t("care_guide_conditions_note")}
      </p>
      <ul className="mt-3 space-y-2">
        {result.conditions.map((condition) => (
          <li
            key={condition.code}
            className="rounded-lg border border-n200 bg-white p-4"
          >
            <div className="flex items-baseline justify-between gap-3">
              <p className="min-w-0 text-body-lg font-medium text-n900">
                {say(condition.names)}
              </p>
              <p className="shrink-0 text-body tabular-nums text-n600">
                {t("care_guide_condition_share", {
                  percent: Math.round(condition.share * 100),
                })}
              </p>
            </div>
            {condition.advice && (
              <p className="mt-1 text-body text-n700">{say(condition.advice)}</p>
            )}
          </li>
        ))}
      </ul>

      {result.recommendation && (
        <WhereToGo service={result.recommendation} coords={coords} lang={lang} />
      )}

      <Disclaimer text={say(result.disclaimer)} />
    </div>
  )
}

/**
 * Facilities providing the recommended service, with the three things asked
 * for: who works there, what insurance they take, and the queue right now.
 */
function WhereToGo({
  service,
  coords,
  lang,
}: {
  service: string
  coords: { lat: number; lng: number } | null
  lang: string
}) {
  const { t } = useI18n()
  const nearby = useNearbyFacilities(coords, { service })
  const facilities = (nearby.data?.results ?? []).slice(0, 3)

  if (nearby.isLoading) {
    return (
      <div className="mt-6">
        <ListSkeleton rows={2} />
      </div>
    )
  }
  if (facilities.length === 0) return null

  return (
    <section className="mt-8">
      <h2 className="text-h3">{t("cg_where_to_go")}</h2>
      <ul className="mt-3 space-y-3">
        {facilities.map((facility) => (
          <li key={facility.slug}>
            <Card className="p-4">
              <Link
                to={`/facility/${facility.slug}`}
                className="text-body-lg font-medium text-n900 hover:text-primary"
              >
                {facility.name}
              </Link>
              <p className="mt-1 flex items-center gap-1.5 text-body text-n600">
                <IconPin size={14} />
                {facility.distance_m != null
                  ? `${(facility.distance_m / 1000).toFixed(1)} km`
                  : facility.district}
              </p>

              {/* The queue, honestly. `not_reported` is not zero, and a
                  facility that publishes nothing must not look like one with
                  nobody waiting. */}
              <p className="mt-3 flex flex-wrap items-center gap-2 text-body">
                <IconClock size={15} />
                <span className="text-n600">{t("cg_queue_now")}:</span>
                {/* `available` with neither a count nor a figure is still
                    unknown - the status alone is not a number, and rendering
                    "about null min" would be the exact failure this product
                    refuses everywhere else. */}
                {facility.wait?.status === "available" &&
                (facility.wait.people_waiting != null ||
                  facility.wait.minutes != null) ? (
                  <Badge tone="accent">
                    {facility.wait.people_waiting != null
                      ? t("queue_people_waiting", {
                          n: facility.wait.people_waiting,
                        })
                      : t("wait_about", { minutes: facility.wait.minutes! })}
                  </Badge>
                ) : (
                  <Badge tone="unknown">{t("queue_eta_unknown")}</Badge>
                )}
              </p>

              {facility.insurers.length > 0 && (
                <div className="mt-3">
                  <p className="ml-label">{t("cg_insurers_here")}</p>
                  <div className="mt-1 flex flex-wrap gap-1.5">
                    {facility.insurers.map((code) => (
                      <Badge key={code} tone="neutral">
                        {code}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              <FacilityDoctors slug={facility.slug} lang={lang} />
            </Card>
          </li>
        ))}
      </ul>
    </section>
  )
}

/** Who works there. Rendered only when the facility actually lists somebody. */
function FacilityDoctors({ slug, lang }: { slug: string; lang: string }) {
  const { t } = useI18n()
  const providers = useQuery({
    queryKey: ["facility-providers", slug],
    queryFn: () => api.facilityProviders(slug),
    staleTime: 5 * 60_000,
  })

  const doctors = (providers.data?.results ?? []).slice(0, 3)
  if (doctors.length === 0) return null

  return (
    <div className="mt-3">
      <p className="ml-label">{t("cg_doctors_here")}</p>
      <ul className="mt-1 space-y-1">
        {doctors.map((doctor) => (
          <li key={doctor.slug} className="flex items-center gap-2 text-body">
            <IconStethoscope size={14} />
            <Link
              to={`/doctor/${doctor.slug}`}
              className="text-n700 hover:text-primary hover:underline"
            >
              {doctor.display_name}
            </Link>
            {doctor.specialties?.[0] && (
              <span className="text-n600">
                ·{" "}
                {lang === "rw"
                  ? doctor.specialties[0].name_rw
                  : lang === "fr"
                    ? doctor.specialties[0].name_fr
                    : doctor.specialties[0].name_en}
              </span>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}

/**
 * Served by the backend, in the patient's language, alongside every response.
 * Never paraphrased here - a clinician approved this wording.
 */
function Disclaimer({ text }: { text: string }) {
  if (!text) return null
  return (
    <p className="mt-8 border-t border-n200 pt-4 text-body font-medium text-n700">
      {text}
    </p>
  )
}
