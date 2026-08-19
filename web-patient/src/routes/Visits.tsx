import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link } from "react-router-dom"
import { api } from "../api/client"
import { useI18n } from "../i18n"
import { useAuth } from "../hooks/useAuth"
import { AppointmentCard } from "../components/AppointmentCard"

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
        <p className="mb-4 text-sm text-neutral-600">{t("auth_prompt")}</p>
        <Link to="/sign-in" className="btn-primary w-full">
          {t("auth_sign_in")}
        </Link>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-md px-4 pb-24 pt-4">
      <h1 className="mb-4 text-xl font-semibold">{t("visits_title")}</h1>

      <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-neutral-500">
        {t("visits_upcoming")}
      </h2>
      {upcoming.data?.length === 0 && (
        <p className="mb-6 text-sm text-neutral-500">{t("visits_none")}</p>
      )}
      {upcoming.data?.map((appointment) => (
        <AppointmentCard
          key={appointment.id}
          appointment={appointment}
          onCancel={() => cancel.mutate(appointment.id)}
        />
      ))}

      <h2 className="mb-2 mt-6 text-sm font-semibold uppercase tracking-wide text-neutral-500">
        {t("visits_past")}
      </h2>
      {past.data?.length === 0 && (
        <p className="text-sm text-neutral-500">{t("visits_none")}</p>
      )}
      {past.data?.map((appointment) => (
        <div key={appointment.id} className="card mb-2 flex justify-between">
          <div>
            <p className="font-medium">{appointment.facility.name}</p>
            <p className="text-sm text-neutral-500">
              {new Date(appointment.slot_start).toLocaleDateString()}
            </p>
          </div>
          <span className="self-center text-sm text-neutral-500">
            {t(`appt_status_${appointment.status}`)}
          </span>
        </div>
      ))}
    </div>
  )
}
