import { useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { useMutation, useQuery } from "@tanstack/react-query"
import { ProgressSteps } from "../components/ProgressSteps"
import { api, ApiRequestError } from "../api/client"
import { useI18n } from "../i18n"
import { useTriageStatus } from "../hooks/useTriageStatus"
import type { TriageSession, Translation } from "../api/types"
import { Card, Chip, ErrorState, ListSkeleton, Notice } from "../ui"

/**
 * The Care Guide.
 *
 * Four rules govern this screen, and none of them are negotiable.
 *
 * 1. IT NEVER DIAGNOSES. It suggests which service to attend. The word
 *    "diagnosis" does not appear, and neither does any condition name - the
 *    protocol only ever returns a service code.
 * 2. THE DISCLAIMER IS ON EVERY STEP, in the patient's own language, served
 *    by the backend alongside each response rather than written here. A
 *    clinician approves the wording; the client does not get to paraphrase it.
 * 3. A RED FLAG ENDS THE FLOW IMMEDIATELY. `escalate_emergency` abandons
 *    everything and shows emergency guidance. No further questions, no way
 *    back into the flow, and the backend refuses to modify an escalated
 *    session even if a later answer arrives.
 * 4. IF THE GATE IS SHUT, THIS SCREEN IS NOT REACHABLE. Entry points are
 *    hidden when `/triage/status` reports unavailable. Somebody arriving here
 *    by typing the URL gets an honest explanation, never a broken flow.
 */
export function CareGuide() {
  const { t, lang } = useI18n()
  const navigate = useNavigate()
  const status = useTriageStatus()

  const [session, setSession] = useState<TriageSession | null>(null)
  const [answered, setAnswered] = useState(0)

  const start = useMutation({
    mutationFn: api.triageStart,
    onSuccess: (data) => {
      setSession(data)
      setAnswered(0)
    },
  })

  const answer = useMutation({
    mutationFn: ({ question, option }: { question: string; option: string }) =>
      api.triageAnswer(session!.session_id, question, option),
    onSuccess: (data) => {
      setSession(data)
      setAnswered((n) => n + 1)
    },
  })

  const say = (text: Translation | null | undefined) =>
    text ? (text[lang] ?? text.en) : ""

  // ------------------------------------------------------------- gate shut
  if (status.isLoading) {
    return (
      <div className="ml-page py-6">
        <ListSkeleton rows={1} />
      </div>
    )
  }

  if (!status.available) {
    return (
      <div className="mx-auto w-full max-w-xl px-4 py-6 pb-24 md:pb-10">
        <h1 className="text-h1">{t("care_guide")}</h1>
        <div className="mt-4">
          {/* Not an error. Nothing is broken - the feature is waiting on a
              clinician, and saying so plainly is more trustworthy than a
              spinner or a "try again later". */}
          <Notice tone="info">
            {status.reason || t("care_guide_unavailable")}
          </Notice>
        </div>
        <p className="mt-4 text-body text-ink-muted">
          {t("care_guide_unavailable_body")}
        </p>
        <div className="mt-6 flex flex-wrap gap-2">
          <Link to="/search" className="ml-btn-primary">
            {t("find_care")}
          </Link>
          <Link to="/" className="ml-btn-secondary">
            {t("nav_home")}
          </Link>
        </div>
      </div>
    )
  }

  // -------------------------------------------------------------- emergency
  if (session?.escalate_emergency) {
    return (
      <Emergency
        advice={say(session.emergency_advice)}
        disclaimer={say(session.disclaimer)}
      />
    )
  }

  // ----------------------------------------------------------------- result
  if (session?.finished) {
    return (
      <Result
        recommendation={session.recommendation}
        disclaimer={say(session.disclaimer)}
        onRestart={() => {
          setSession(null)
          start.reset()
        }}
        onFind={(service) => navigate(`/search?service=${service}`)}
      />
    )
  }

  // --------------------------------------------------------------- landing
  if (!session) {
    return (
      <div className="mx-auto w-full max-w-xl px-4 py-6 pb-24 md:pb-10">
        <h1 className="text-h1">{t("care_guide")}</h1>
        <p className="mt-2 text-body text-ink-muted">{t("care_guide_intro")}</p>

        <Card className="mt-6 p-4">
          <h2 className="text-h3">{t("care_guide_what_it_does")}</h2>
          <ul className="mt-3 space-y-2 text-body">
            <li>{t("care_guide_point_1")}</li>
            <li>{t("care_guide_point_2")}</li>
            <li>{t("care_guide_point_3")}</li>
          </ul>
        </Card>

        <div className="mt-4">
          <Notice tone="warning">{t("care_guide_emergency_first")}</Notice>
        </div>

        <button
          className="ml-btn-primary mt-6 w-full"
          disabled={start.isPending}
          onClick={() => start.mutate()}
        >
          {t("care_guide_start")}
        </button>

        {/* Paced by the real request, not a scripted delay - see
            ProgressSteps. On a fast connection this is one frame. */}
        {start.isPending && (
          <ProgressSteps
            className="mt-4"
            steps={[
              t("care_guide_step_preparing"),
              t("care_guide_step_pathways"),
            ]}
          />
        )}

        {start.isError && <StartError error={start.error} />}

        <p className="mt-4 text-caption text-ink-subtle">
          {t("care_guide_privacy")}
        </p>
      </div>
    )
  }

  // ------------------------------------------------------------- questions
  const question = session.next_question
  if (!question) {
    // finished/escalate are handled above, so this is a protocol that ran out
    // of questions without reaching an outcome. Say so rather than hanging.
    return (
      <div className="ml-page py-6">
        <ErrorState
          title={t("care_guide_incomplete")}
          action={
            <Link to="/search" className="ml-btn-primary ml-btn-sm">
              {t("find_care")}
            </Link>
          }
        />
      </div>
    )
  }

  return (
    <div className="mx-auto w-full max-w-xl px-4 py-6 pb-24 md:pb-10">
      {/* Staged progress. The total is unknown - the protocol branches - so
          this counts what has been answered rather than faking a bar that
          would jump backwards when a branch turns out to be longer. */}
      <p className="text-small text-ink-muted">
        {t("care_guide_question_n", { n: answered + 1 })}
      </p>

      {/* Marking a screening question as urgent risks priming the answer -
          somebody frightened may say yes to be safe. Kept anyway: an
          unnecessary trip to a hospital is a far cheaper mistake than a missed
          red flag, and the label tells a patient skimming to slow down. */}
      {question.red_flag && (
        <div className="mt-3">
          <Chip tone="warning">{t("care_guide_urgent_check")}</Chip>
        </div>
      )}

      <h1 className="mt-3 text-h2">{say(question.text)}</h1>

      <ul className="mt-6 space-y-2">
        {question.options.map((option) => (
          <li key={option.code}>
            <button
              className="ml-btn-secondary w-full justify-start text-left"
              disabled={answer.isPending}
              onClick={() =>
                answer.mutate({ question: question.code, option: option.code })
              }
            >
              {say(option.text)}
            </button>
          </li>
        ))}
      </ul>

      {/* Same rule as the start button: the steps are paced by the request,
          so a fast answer shows one line and a slow one explains itself. */}
      {answer.isPending && (
        <ProgressSteps
          className="mt-4"
          steps={[
            t("care_guide_step_reviewing"),
            t("care_guide_step_pathways"),
            t("care_guide_step_specialists"),
          ]}
        />
      )}

      {answer.isError && (
        <div className="mt-4">
          <ErrorState
            title={t("error_generic")}
            action={
              <button
                className="ml-btn-secondary ml-btn-sm"
                onClick={() => {
                  setSession(null)
                  answer.reset()
                }}
              >
                {t("care_guide_start_over")}
              </button>
            }
          />
        </div>
      )}

      {/* Rule 2: every step, not once at the start. */}
      <Disclaimer text={say(session.disclaimer)} />

      <button
        className="ml-btn-tertiary mt-4 w-full"
        onClick={() => {
          setSession(null)
          answer.reset()
        }}
      >
        {t("care_guide_stop")}
      </button>
    </div>
  )
}

/* ------------------------------------------------------------------------ */

function Emergency({
  advice,
  disclaimer,
}: {
  advice: string
  disclaimer: string
}) {
  const { t } = useI18n()
  return (
    <div className="mx-auto w-full max-w-xl px-4 py-6 pb-24 md:pb-10">
      {/* The flow is over. There is deliberately no way back into it - a
          patient who has been told to seek emergency care must not be able to
          answer their way out of that advice. */}
      <div className="rounded-xl border border-danger-border bg-danger-subtle p-5">
        <p className="text-caption font-semibold uppercase tracking-widest text-danger">
          {t("care_guide_emergency_label")}
        </p>
        <p className="mt-2 text-h2 text-danger">{advice}</p>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        {/* The number lives in the language bundle, not here: it is
            safety-critical and must be correctable without a code change. */}
        <a className="ml-btn-primary flex-1" href={`tel:${t("emergency_number")}`}>
          {t("care_guide_call_912", { number: t("emergency_number") })}
        </a>
        <Link to="/search?level=hospital" className="ml-btn-secondary flex-1">
          {t("care_guide_nearest_hospital")}
        </Link>
      </div>

      <Disclaimer text={disclaimer} />
    </div>
  )
}

function Result({
  recommendation,
  disclaimer,
  onRestart,
  onFind,
}: {
  recommendation: string | null
  disclaimer: string
  onRestart: () => void
  onFind: (service: string) => void
}) {
  const { t, lang } = useI18n()

  // The protocol returns a service CODE. Its patient-facing name comes from
  // the backend, which holds all three languages - t() would return the key
  // itself for an unknown service, and a screen reading "service_dialysis"
  // helps nobody.
  const serviceTypes = useQuery({
    queryKey: ["service-types"],
    queryFn: api.serviceTypes,
    staleTime: 60 * 60_000,
    enabled: recommendation !== null,
  })

  const match = serviceTypes.data?.results.find(
    (service) => service.code === recommendation,
  )
  const label = match
    ? (lang === "rw" ? match.name_rw : lang === "fr" ? match.name_fr : match.name_en)
    : recommendation
      ? humanise(recommendation)
      : ""

  return (
    <div className="mx-auto w-full max-w-xl px-4 py-6 pb-24 md:pb-10">
      <h1 className="text-h1">{t("care_guide_result_title")}</h1>

      {recommendation ? (
        <>
          <Card className="mt-4 p-5">
            <p className="text-small text-ink-muted">
              {t("care_guide_suggests")}
            </p>
            <p className="mt-1 text-h2">{label}</p>
            <p className="mt-3 text-body text-ink-muted">
              {t("care_guide_result_body")}
            </p>
          </Card>

          {/* The journey continues rather than ending on a dead result: this
              service code is exactly the filter the search screen takes. */}
          <button
            className="ml-btn-primary mt-4 w-full"
            onClick={() => onFind(recommendation)}
          >
            {t("care_guide_find_nearby", { service: label })}
          </button>
        </>
      ) : (
        <Notice tone="info">{t("care_guide_no_recommendation")}</Notice>
      )}

      <div className="mt-3 flex flex-wrap gap-2">
        <Link to="/doctors" className="ml-btn-secondary flex-1">
          {t("nav_doctors")}
        </Link>
        <button className="ml-btn-tertiary flex-1" onClick={onRestart}>
          {t("care_guide_start_over")}
        </button>
      </div>

      <Disclaimer text={disclaimer} />
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
    <p className="mt-6 border-t border-line pt-4 text-caption text-ink-subtle">
      {text}
    </p>
  )
}

function StartError({ error }: { error: unknown }) {
  const { t } = useI18n()
  // A 503 here means the gate closed between the status check and the start -
  // a deploy, or a withdrawn approval. Not an error the patient can retry.
  const gated =
    error instanceof ApiRequestError && error.status === 503
  return (
    <div className="mt-4">
      {gated ? (
        <Notice tone="info">{t("care_guide_unavailable")}</Notice>
      ) : (
        <ErrorState title={t("error_generic")} />
      )}
    </div>
  )
}

function humanise(code: string) {
  return code.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase())
}
