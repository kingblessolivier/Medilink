import { useI18n } from "../i18n"
import type { Appointment } from "../api/types"

/** Home screen state C - an appointment booked for today. */
export function AppointmentCard({
  appointment,
  onCancel,
}: {
  appointment: Appointment
  onCancel?: () => void
}) {
  const { t } = useI18n()
  const start = new Date(appointment.slot_start)
  const isToday = start.toDateString() === new Date().toDateString()

  const directions =
    "https://www.google.com/maps/dir/?api=1&destination=" +
    encodeURIComponent(appointment.facility.name)

  return (
    <section className="card mb-4">
      <p className="text-sm text-neutral-500">
        {isToday
          ? t("appt_today_at", {
              time: start.toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
              }),
            })
          : start.toLocaleString([], {
              weekday: "short",
              day: "numeric",
              month: "short",
              hour: "2-digit",
              minute: "2-digit",
            })}
      </p>

      <h3 className="mt-1 text-lg font-semibold">{appointment.facility.name}</h3>

      <p className="mt-1 text-sm text-neutral-500">
        {t("appt_reference")}:{" "}
        <span className="font-mono font-medium text-neutral-700">
          {appointment.reference}
        </span>
      </p>

      <div className="mt-3 flex gap-2">
        <a
          className="btn-secondary flex-1"
          href={directions}
          target="_blank"
          rel="noreferrer"
        >
          {t("directions")}
        </a>
        {appointment.facility.phone && (
          <a
            className="btn-secondary flex-1"
            href={`tel:${appointment.facility.phone}`}
          >
            {t("call")}
          </a>
        )}
        {onCancel && (
          <button className="btn-secondary flex-1" onClick={onCancel}>
            {t("cancel")}
          </button>
        )}
      </div>
    </section>
  )
}
