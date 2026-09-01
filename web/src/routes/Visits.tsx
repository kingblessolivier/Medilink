import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { IconCalendar } from "../ui/icons"
import { Link } from "react-router-dom"
import { api } from "../api/client"
import { useI18n } from "../i18n"
import { useAuth } from "../hooks/useAuth"
import { AppointmentCard } from "../components/AppointmentCard"
import { Card, EmptyState, ErrorState, ListSkeleton } from "../ui"

/**
 * Appointments, upcoming and past.
 *
 * The two lists load independently, so they get their own loading and error
 * states: a failure fetching history must not hide the appointment somebody
 * has this afternoon.
 */
export function Visits() {
  const { t } = useI18n()
  const { session } = useAuth()
  const queryClient = useQueryClient()
  const signedIn = session.state === "signed_in"

  const upcoming = useQuery({
    queryKey: ["appointments", "upcoming"],
    queryFn: () => api.appointments("upcoming"),
    enabled: signedIn,
  })

  const past = useQuery({
    queryKey: ["appointments", "past"],
    queryFn: () => api.appointments("past"),
    enabled: signedIn,
  })

  const cancel = useMutation({
    mutationFn: api.cancelAppointment,
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["appointments"] }),
  })

  if (!signedIn) {
    return (
      <div className="mx-auto max-w-md px-4 pt-8 text-center">
        {/* Every page states where it is. Without an h1 a screen-reader user
            has nothing to jump to and no idea which screen they landed on. */}
        <h1 className="mb-2 text-h1">{t("visits_title")}</h1>
        <p className="mb-4 text-small text-ink-muted">{t("auth_prompt")}</p>
        <Link to={`/sign-in?next=${encodeURIComponent("/visits")}`} className="ml-btn-primary w-full">
          {t("auth_sign_in")}
        </Link>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-md px-4 pb-24 md:pb-10 pt-4">
      <h1 className="mb-4 text-h1">{t("visits_title")}</h1>

      {cancel.isError && (
        <div className="mb-4">
          <ErrorState title={t("visits_cancel_failed")} />
        </div>
      )}

      {/* ------------------------------------------------------ upcoming */}
      <h2 className="text-h3 mb-2">{t("visits_upcoming")}</h2>

      {upcoming.isLoading && <ListSkeleton rows={1} />}

      {upcoming.isError && (
        <ErrorState
          title={t("visits_load_failed")}
          action={
            <button
              className="ml-btn-secondary ml-btn-sm"
              onClick={() => upcoming.refetch()}
            >
              {t("retry")}
            </button>
          }
        />
      )}

      {upcoming.data?.length === 0 && (
        <EmptyState icon={<IconCalendar size={20} />}
          title={t("visits_none")}
          body={t("visits_none_body")}
          action={
            <Link to="/search" className="ml-btn-primary ml-btn-sm">
              {t("find_care")}
            </Link>
          }
        />
      )}

      {upcoming.data?.map((appointment) => (
        <AppointmentCard
          key={appointment.id}
          appointment={appointment}
          onCancel={() => cancel.mutate(appointment.id)}
        />
      ))}

      {/* ---------------------------------------------------------- past */}
      <h2 className="text-h3 mb-2 mt-6">{t("visits_past")}</h2>

      {past.isLoading && <ListSkeleton rows={2} />}

      {past.isError && (
        <ErrorState
          title={t("visits_load_failed")}
          action={
            <button
              className="ml-btn-secondary ml-btn-sm"
              onClick={() => past.refetch()}
            >
              {t("retry")}
            </button>
          }
        />
      )}

      {past.data?.length === 0 && <EmptyState icon={<IconCalendar size={20} />} title={t("visits_none_past")} />}

      {past.data?.map((appointment) => (
        <Card key={appointment.id} className="mb-2 flex justify-between p-4">
          <div>
            <p className="font-medium">{appointment.facility.name}</p>
            <p className="text-small tabular-nums text-ink-muted">
              {new Date(appointment.slot_start).toLocaleDateString()}
            </p>
          </div>
          <span className="self-center text-small text-ink-muted">
            {t(`appt_status_${appointment.status}`)}
          </span>
        </Card>
      ))}
    </div>
  )
}
