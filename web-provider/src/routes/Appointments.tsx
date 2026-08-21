import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api, type AppointmentAction, type StaffAppointment } from "../api/client"
import { Chip, EmptyState, ErrorState, TableSkeleton } from "../ui"

/**
 * Who is expected today.
 *
 * A working list, so it opens on today and hides cancelled rows - reception
 * does not need to scroll past appointments nobody is coming to. Cancelled
 * ones are one filter away and still counted in the reports.
 *
 * The phone number is on the row rather than behind a click, because the whole
 * reason to look at this screen at 11am is to ring the people who have not
 * turned up.
 */

const STATUS_TONE = {
  booked: "neutral",
  arrived: "success",
  served: "success",
  no_show: "warning",
  cancelled: "neutral",
} as const

const STATUS_LABEL: Record<string, string> = {
  booked: "Booked",
  arrived: "Arrived",
  served: "Served",
  no_show: "No show",
  cancelled: "Cancelled",
}

const VIA_LABEL: Record<string, string> = {
  app: "App",
  ussd: "USSD",
  whatsapp: "WhatsApp",
  desk: "Desk",
}

function today() {
  // Local date, not toISOString() - that converts to UTC and can hand the
  // backend yesterday for anyone east of Greenwich, which Rwanda is.
  const now = new Date()
  return [
    now.getFullYear(),
    String(now.getMonth() + 1).padStart(2, "0"),
    String(now.getDate()).padStart(2, "0"),
  ].join("-")
}

export function Appointments({ canManage }: { canManage: boolean }) {
  const [date, setDate] = useState(today)
  const [showCancelled, setShowCancelled] = useState(false)
  const queryClient = useQueryClient()

  const params = { date, ...(showCancelled ? { status: "cancelled" } : {}) }

  const query = useQuery({
    queryKey: ["appointments", date, showCancelled],
    queryFn: () => api.appointments(params),
    refetchInterval: 60_000,
  })

  const update = useMutation({
    mutationFn: ({ id, status }: { id: number; status: AppointmentAction }) =>
      api.setAppointmentStatus(id, status),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["appointments"] }),
  })

  const rows = query.data?.results ?? []
  const expected = rows.filter((r) => r.status === "booked").length

  return (
    <div className="mx-auto w-full max-w-5xl">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-h2">Appointments</h1>
          <p className="mt-1 text-small text-ink-muted">
            {query.isLoading
              ? " "
              : `${rows.length} booked · ${expected} still expected`}
          </p>
        </div>

        <div className="flex items-end gap-3">
          <label className="block">
            <span className="ml-label block">Date</span>
            <input
              type="date"
              className="ml-field mt-1"
              value={date}
              onChange={(e) => setDate(e.target.value || today())}
            />
          </label>
          <button
            className="ml-btn-secondary ml-btn-sm mb-0.5"
            onClick={() => setDate(today())}
          >
            Today
          </button>
        </div>
      </div>

      <label className="mt-3 flex items-center gap-2 text-small text-ink-muted">
        <input
          type="checkbox"
          className="h-4 w-4 accent-primary"
          checked={showCancelled}
          onChange={(e) => setShowCancelled(e.target.checked)}
        />
        Show cancelled instead
      </label>

      {update.isError && (
        <div className="mt-3">
          <ErrorState title={(update.error as Error).message} />
        </div>
      )}

      <div className="mt-4">
        {query.isLoading && <TableSkeleton rows={4} />}

        {query.isError && (
          <ErrorState
            title="Could not load the appointment list."
            action={
              <button
                className="ml-btn-secondary ml-btn-sm"
                onClick={() => query.refetch()}
              >
                Try again
              </button>
            }
          />
        )}

        {query.isSuccess && rows.length === 0 && (
          <EmptyState
            title={
              showCancelled
                ? "Nothing cancelled on this date."
                : "No appointments booked for this date."
            }
            body="Walk-in patients are checked in from Reception."
          />
        )}

        {rows.length > 0 && (
          <div className="overflow-x-auto rounded-lg border border-line bg-surface">
            <table className="ml-table">
              <thead>
                <tr>
                  <th scope="col">Time</th>
                  <th scope="col">Patient</th>
                  <th scope="col">Service</th>
                  <th scope="col">Doctor</th>
                  <th scope="col">Booked</th>
                  <th scope="col">Status</th>
                  {canManage && (
                    <th scope="col">
                      <span className="sr-only">Actions</span>
                    </th>
                  )}
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <Row
                    key={row.id}
                    row={row}
                    canManage={canManage}
                    busy={update.isPending}
                    onSet={(status) => update.mutate({ id: row.id, status })}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

function Row({
  row,
  canManage,
  busy,
  onSet,
}: {
  row: StaffAppointment
  canManage: boolean
  busy: boolean
  onSet: (status: AppointmentAction) => void
}) {
  // Cancelled and served are finished. A no-show is NOT: somebody mis-taps at
  // a busy desk, or the patient turns up twenty minutes late, and reception
  // needs to put that right without ringing support.
  const finished = row.status === "cancelled" || row.status === "served"

  return (
    <tr>
      <td className="tabular-nums whitespace-nowrap">
        {new Date(row.slot_start).toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        })}
      </td>

      <td>
        <span className="block">{row.patient_name}</span>
        {row.patient_phone ? (
          // A link, not text: on a desk phone or a tablet this is one tap.
          <a
            className="text-small tabular-nums text-ink-muted underline"
            href={`tel:${row.patient_phone}`}
          >
            {row.patient_phone}
          </a>
        ) : (
          <span className="text-small text-ink-subtle">
            Record removed at the patient's request
          </span>
        )}
      </td>

      <td>{row.service}</td>
      <td className="text-ink-muted">{row.provider ?? "—"}</td>
      <td className="text-ink-muted">
        {VIA_LABEL[row.booked_via] ?? row.booked_via}
      </td>

      <td>
        <Chip tone={STATUS_TONE[row.status as keyof typeof STATUS_TONE]}>
          {STATUS_LABEL[row.status] ?? row.status}
        </Chip>
      </td>

      {canManage && (
        <td className="whitespace-nowrap text-right">
          {/* Nothing repeated from the Status column - it is two cells away. */}
          {finished ? null : (
            <span className="flex justify-end gap-1">
              {row.status === "booked" && (
                <button
                  className="ml-btn-secondary ml-btn-sm"
                  disabled={busy}
                  onClick={() => onSet("arrived")}
                >
                  Arrived
                </button>
              )}
              {row.status === "arrived" && (
                <button
                  className="ml-btn-secondary ml-btn-sm"
                  disabled={busy}
                  onClick={() => onSet("served")}
                >
                  Served
                </button>
              )}
              {row.status === "no_show" ? (
                <button
                  className="ml-btn-tertiary ml-btn-sm"
                  disabled={busy}
                  onClick={() => onSet("arrived")}
                >
                  They arrived after all
                </button>
              ) : (
                <button
                  className="ml-btn-tertiary ml-btn-sm"
                  disabled={busy}
                  onClick={() => onSet("no_show")}
                >
                  No show
                </button>
              )}
            </span>
          )}
        </td>
      )}
    </tr>
  )
}
