import { Link, useParams, useSearchParams } from "react-router-dom"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "../api/client"
import { useI18n } from "../i18n"
import { Button, Card, Chip, ErrorState, ListSkeleton, Notice } from "../ui"
import type { Appointment } from "../api/types"

/**
 * One appointment, and the confirmation screen.
 *
 * `?new=1` after booking turns this into a receipt. Same screen either way -
 * a separate confirmation page would be a screen a patient sees once and can
 * never get back to, and the reference code is exactly the thing they need to
 * find again.
 */
export function AppointmentDetail() {
  const { id = "" } = useParams()
  const [params] = useSearchParams()
  const { t } = useI18n()
  const queryClient = useQueryClient()
  const justBooked = params.get("new") === "1"

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["appointment", id],
    queryFn: () => api.appointment(Number(id)),
    staleTime: 30_000,
  })

  const cancel = useMutation({
    mutationFn: () => api.cancelAppointment(Number(id)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["appointment", id] })
      queryClient.invalidateQueries({ queryKey: ["appointments"] })
    },
  })

  if (isLoading) {
    return (
      <div className="ml-page py-6">
        <ListSkeleton rows={1} />
      </div>
    )
  }

  if (isError || !data) {
    return (
      <div className="ml-page py-6">
        <ErrorState
          title={t("error_generic")}
          action={
            <Button size="sm" onClick={() => refetch()}>
              {t("retry")}
            </Button>
          }
        />
      </div>
    )
  }

  const start = new Date(data.slot_start)
  const cancelled = data.status === "cancelled"
  const past = start.getTime() < Date.now()

  return (
    <div className="mx-auto w-full max-w-xl px-4 py-6 pb-24 md:pb-10">
      <Link to="/visits" className="text-small font-medium text-primary">
        {t("back")}
      </Link>

      {justBooked && !cancelled && (
        <div className="mt-3">
          <Notice tone="info">{t("booking_confirmed")}</Notice>
        </div>
      )}

      <Card className="mt-4 p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="ml-label">{t("next_appointment")}</p>
            {/* The time IS the heading here - it is what somebody opens this
                screen to read - so it carries the h1 rather than having a
                second, quieter title above it. */}
            <h1 className="mt-1 text-h1">
              {start.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
            </h1>
            <p className="text-body-lg text-ink-muted">
              {start.toLocaleDateString(undefined, {
                weekday: "long",
                day: "numeric",
                month: "long",
              })}
            </p>
          </div>
          <StatusChip appointment={data} />
        </div>

        <dl className="mt-5 divide-y divide-line border-t border-line">
          <Line label={t("facility_information")}>
            <Link
              to={`/facility/${data.facility.slug}`}
              className="text-primary hover:underline"
            >
              {data.facility.name}
            </Link>
          </Line>
          <Line label={t("tab_services")}>{data.service.replace(/_/g, " ")}</Line>
          <Line label={t("choose_doctor")}>
            {data.provider ?? t("any_available")}
          </Line>
          <Line label={t("reference")}>
            {/* Read aloud at a reception desk, so it is monospaced and
                deliberately large. */}
            <span className="font-mono text-body-lg tracking-wide">
              {data.reference}
            </span>
          </Line>
        </dl>

        {!cancelled && !past && (
          <>
            <div className="mt-5 flex flex-wrap gap-2">
              <Link
                to={`/facility/${data.facility.slug}`}
                className="ml-btn-secondary ml-btn-sm"
              >
                {t("view_facility")}
              </Link>
              {data.facility.phone && (
                <a
                  href={`tel:${data.facility.phone}`}
                  className="ml-btn-secondary ml-btn-sm"
                >
                  {t("call")}
                </a>
              )}
            </div>

            <div className="mt-5 border-t border-line pt-4">
              {cancel.isError && (
                <div className="mb-3">
                  <ErrorState title={t("error_generic")} />
                </div>
              )}
              {/* One tap, no confirmation dialog. A booking nobody honours is
                  worse than no booking, so cancelling must be easy. */}
              <Button
                variant="destructive"
                size="sm"
                loading={cancel.isPending}
                onClick={() => cancel.mutate()}
              >
                {t("cancel_appointment")}
              </Button>
              <p className="mt-2 text-caption text-ink-subtle">
                {t("cancel_note")}
              </p>
            </div>
          </>
        )}
      </Card>

      {!cancelled && !past && (
        <div className="mt-4">
          <Notice tone="info">{t("appointment_arrival_note")}</Notice>
        </div>
      )}
    </div>
  )
}

function StatusChip({ appointment }: { appointment: Appointment }) {
  const { t } = useI18n()
  const tone =
    appointment.status === "cancelled"
      ? "danger"
      : appointment.status === "no_show"
        ? "warning"
        : appointment.status === "served"
          ? "neutral"
          : "success"

  return <Chip tone={tone}>{t(`appointment_${appointment.status}`)}</Chip>
}

function Line({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-3">
      <dt className="ml-label shrink-0">{label}</dt>
      <dd className="min-w-0 text-right text-body">{children}</dd>
    </div>
  )
}
