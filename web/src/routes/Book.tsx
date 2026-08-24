import { useMemo, useState } from "react"
import { IconCalendar } from "../ui/icons"
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom"
import { useMutation, useQuery } from "@tanstack/react-query"
import { api, ApiRequestError } from "../api/client"
import { useI18n } from "../i18n"
import { specialtyNames } from "../lib/specialty"
import { usePatient } from "../hooks/useAuth"
import { useProviders } from "../hooks/useProviders"
import { useInsurerPreference } from "../hooks/useInsurerPreference"
import { useInsurers } from "../hooks/useNearbyFacilities"
import {
  Button,
  Card,
  Chip,
  EmptyState,
  ErrorState,
  ListSkeleton,
  Notice,
  Skeleton,
} from "../ui"

type Step = "service" | "provider" | "time" | "review"

/**
 * Booking.
 *
 * Four steps, each one screen, each answerable without scrolling. The brief
 * asks for a short flow and the reason is concrete: this is used one-handed,
 * on a phone, often by somebody who is unwell.
 *
 * "Any available" is the default and the first option at the provider step.
 * Naming a clinician narrows availability, and most patients neither need to
 * nor know whom to pick.
 */
export function Book() {
  const { slug = "" } = useParams()
  const { t, lang } = useI18n()
  const navigate = useNavigate()
  const patient = usePatient()
  const [params] = useSearchParams()
  const { insurer } = useInsurerPreference()
  const { data: insurerData } = useInsurers()

  const [service, setService] = useState<string | undefined>(
    params.get("service") ?? undefined,
  )
  const [provider, setProvider] = useState<string | undefined>(undefined)
  const [slot, setSlot] = useState<string | undefined>(undefined)
  const [step, setStep] = useState<Step>(service ? "provider" : "service")

  const facility = useQuery({
    queryKey: ["facility", slug],
    queryFn: () => api.facility(slug),
    staleTime: 60_000,
  })

  const doctors = useProviders(
    { facility: slug, service, limit: 20 },
    Boolean(service),
  )

  const slots = useQuery({
    queryKey: ["slots", slug, service, provider],
    queryFn: () => api.slots(slug, { service: service!, provider }),
    enabled: Boolean(service) && step === "time",
    staleTime: 30_000,
  })

  const booking = useMutation({
    mutationFn: () =>
      api.book({
        facility: slug,
        service: service!,
        provider,
        slot_start: slot!,
      }),
    onSuccess: (appointment) =>
      navigate(`/appointment/${appointment.id}?new=1`, { replace: true }),
  })

  const insurerName = insurerData?.results.find((i) => i.code === insurer)?.name
  const label = (s: { name_rw: string; name_en: string; name_fr: string }) =>
    lang === "rw" ? s.name_rw : lang === "fr" ? s.name_fr : s.name_en

  const chosenService = facility.data?.services.find((s) => s.code === service)
  const chosenDoctor = doctors.data?.results.find((d) => d.slug === provider)

  const days = slots.data?.days ?? []
  const openDays = useMemo(
    () => days.filter((d) => d.slots.some((s) => s.remaining > 0)),
    [days],
  )

  // Signing in is required to book, but discovery is not - so the prompt
  // arrives here rather than at the front door.
  if (!patient) {
    return (
      <div className="mx-auto w-full max-w-xl px-4 py-6">
        {/* Every screen says where it is, in EVERY state. The signed-out
            branch had no h1 at all, so a screen-reader user hitting a booking
            link while logged out landed on a page with no title. */}
        <h1 className="mb-4 text-h1">{t("book_title")}</h1>
        <EmptyState icon={<IconCalendar size={20} />}
          title={t("sign_in_to_book")}
          body={t("sign_in_to_book_body")}
          action={
            <Link to={`/sign-in?next=${encodeURIComponent(`/facility/${slug}/book`)}`} className="ml-btn-primary ml-btn-sm">
              {t("sign_in")}
            </Link>
          }
        />
      </div>
    )
  }

  if (facility.isLoading) {
    return (
      <div className="ml-page py-6">
        <ListSkeleton rows={2} />
      </div>
    )
  }

  if (facility.isError || !facility.data) {
    return (
      <div className="ml-page py-6">
        <ErrorState title={t("error_generic")} />
      </div>
    )
  }

  return (
    <div className="mx-auto w-full max-w-xl px-4 py-6 pb-24">
      <Link to={`/facility/${slug}`} className="text-small font-medium text-primary">
        {t("back")}
      </Link>

      <h1 className="mt-2 text-h1">{t("book_at", { facility: facility.data.name })}</h1>

      <Steps step={step} />

      {/* ------------------------------------------------------- service */}
      {step === "service" && (
        <Section title={t("choose_service")}>
          <ul className="divide-y divide-line rounded-xl border border-line bg-surface">
            {facility.data.services.map((option) => (
              <li key={option.code}>
                <button
                  className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left hover:bg-surface-sunken"
                  onClick={() => {
                    setService(option.code)
                    setProvider(undefined)
                    setSlot(undefined)
                    setStep("provider")
                  }}
                >
                  <span className="text-body">{label(option)}</span>
                  <span aria-hidden="true" className="text-ink-subtle">
                    &rsaquo;
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {/* ------------------------------------------------------ provider */}
      {step === "provider" && (
        <Section title={t("choose_doctor")}>
          <ul className="divide-y divide-line rounded-xl border border-line bg-surface">
            {/* First, and the default. */}
            <li>
              <button
                className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left hover:bg-surface-sunken"
                onClick={() => {
                  setProvider(undefined)
                  setSlot(undefined)
                  setStep("time")
                }}
              >
                <span>
                  <span className="block text-body font-medium">
                    {t("any_available")}
                  </span>
                  <span className="block text-small text-ink-muted">
                    {t("any_available_body")}
                  </span>
                </span>
                <span aria-hidden="true" className="text-ink-subtle">
                  &rsaquo;
                </span>
              </button>
            </li>

            {doctors.data?.results.map((doctor) => (
              <li key={doctor.slug}>
                <button
                  className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left hover:bg-surface-sunken"
                  onClick={() => {
                    setProvider(doctor.slug)
                    setSlot(undefined)
                    setStep("time")
                  }}
                >
                  <span className="min-w-0">
                    <span className="block truncate text-body">
                      {doctor.display_name}
                    </span>
                    <span className="block truncate text-small text-ink-muted">
                      {specialtyNames(doctor.specialties, lang)}
                    </span>
                  </span>
                  <span aria-hidden="true" className="text-ink-subtle">
                    &rsaquo;
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {/* ---------------------------------------------------------- time */}
      {step === "time" && (
        <Section title={t("choose_time")}>
          {slots.isLoading && <Skeleton className="h-40 w-full rounded-xl" />}

          {slots.data && openDays.length === 0 && (
            <EmptyState icon={<IconCalendar size={20} />}
              title={t("no_slots")}
              body={
                provider ? t("no_slots_provider_body") : t("no_slots_body")
              }
              action={
                provider ? (
                  <Button
                    size="sm"
                    onClick={() => {
                      setProvider(undefined)
                      setSlot(undefined)
                    }}
                  >
                    {t("try_any_available")}
                  </Button>
                ) : undefined
              }
            />
          )}

          <div className="space-y-4">
            {openDays.map((day) => (
              <div key={day.date}>
                <p className="ml-label mb-2">
                  {new Date(day.date).toLocaleDateString(undefined, {
                    weekday: "long",
                    day: "numeric",
                    month: "short",
                  })}
                </p>
                <div className="flex flex-wrap gap-2">
                  {day.slots.map((option) => {
                    const full = option.remaining === 0
                    const time = new Date(option.start).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    })
                    return (
                      <button
                        key={option.start}
                        disabled={full}
                        aria-pressed={slot === option.start}
                        onClick={() => {
                          setSlot(option.start)
                          setStep("review")
                        }}
                        className={
                          "min-h-touch rounded-md border px-3 text-body transition-colors " +
                          (full
                            ? "cursor-not-allowed border-line bg-surface-sunken text-ink-subtle line-through"
                            : slot === option.start
                              ? "border-primary bg-primary text-white"
                              : "border-line-strong bg-surface hover:bg-surface-sunken")
                        }
                      >
                        {time}
                      </button>
                    )
                  })}
                </div>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* -------------------------------------------------------- review */}
      {step === "review" && (
        <Section title={t("review_booking")}>
          <Card className="divide-y divide-line">
            <Line label={t("facility_information")}>{facility.data.name}</Line>
            <Line label={t("tab_services")}>
              {chosenService ? label(chosenService) : service}
            </Line>
            <Line label={t("choose_doctor")}>
              {chosenDoctor ? chosenDoctor.display_name : t("any_available")}
            </Line>
            <Line label={t("choose_time")}>
              {slot
                ? new Date(slot).toLocaleString(undefined, {
                    weekday: "long",
                    day: "numeric",
                    month: "short",
                    hour: "2-digit",
                    minute: "2-digit",
                  })
                : "-"}
            </Line>
            <Line label={t("filter_insurer")}>
              {insurerName ? (
                <Chip tone="neutral">{insurerName}</Chip>
              ) : (
                <span className="text-ink-muted">{t("no_cover_set")}</span>
              )}
            </Line>
          </Card>

          {/* We hold facility-declared acceptance, never eligibility. */}
          <div className="mt-3">
            <Notice tone="info">{t("booking_insurance_note")}</Notice>
          </div>

          {booking.isError && (
            <div className="mt-3">
              <ErrorState
                title={
                  booking.error instanceof ApiRequestError &&
                  booking.error.status === 409
                    ? t("slot_taken")
                    : t("error_generic")
                }
                body={
                  booking.error instanceof ApiRequestError
                    ? booking.error.message
                    : undefined
                }
                action={
                  <Button
                    size="sm"
                    onClick={() => {
                      setSlot(undefined)
                      setStep("time")
                      slots.refetch()
                    }}
                  >
                    {t("choose_another_time")}
                  </Button>
                }
              />
            </div>
          )}

          <div className="mt-4 flex gap-2">
            <Button variant="secondary" onClick={() => setStep("time")}>
              {t("back")}
            </Button>
            <Button
              variant="primary"
              full
              loading={booking.isPending}
              onClick={() => booking.mutate()}
            >
              {t("confirm_booking")}
            </Button>
          </div>
        </Section>
      )}
    </div>
  )
}

const ORDER: Step[] = ["service", "provider", "time", "review"]

function Steps({ step }: { step: Step }) {
  const { t } = useI18n()
  const index = ORDER.indexOf(step)

  return (
    <ol className="mt-4 flex gap-1.5" aria-label={t("progress")}>
      {ORDER.map((name, position) => (
        <li
          key={name}
          aria-current={position === index ? "step" : undefined}
          className={
            "h-1.5 flex-1 rounded-full " +
            (position <= index ? "bg-primary" : "bg-surface-sunken")
          }
        />
      ))}
    </ol>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-6">
      <h2 className="text-h3 mb-3">{title}</h2>
      {children}
    </section>
  )
}

function Line({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 px-4 py-3">
      <span className="ml-label shrink-0">{label}</span>
      <span className="min-w-0 text-right text-body">{children}</span>
    </div>
  )
}
