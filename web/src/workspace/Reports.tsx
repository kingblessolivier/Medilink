import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { api, type FacilityReport } from "../api/client"
import { Chip, ErrorState, Notice, TableSkeleton } from "../ui"

/**
 * What this facility's own numbers say.
 *
 * docs/09: this screen is how a facility decides to keep using MediLink, so
 * every figure on it is measured rather than modelled. Where the sample is too
 * thin to be honest, the number is REPLACED by a sentence explaining that -
 * not printed with a caveat beside it. A manager acts on whatever number is on
 * the screen, so there must not be one.
 *
 * The same rule the patient-facing wait times follow. See docs/11 section 7.
 */

const WINDOWS = [7, 30, 90] as const

export function WorkspaceReports() {
  const [days, setDays] = useState<number>(30)

  const query = useQuery({
    queryKey: ["reports", days],
    queryFn: () => api.staffReports(days),
    staleTime: 5 * 60_000,
  })

  return (
    <div className="mx-auto w-full max-w-5xl">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-h2">Reports</h1>
          <p className="mt-1 text-small text-ink-muted">
            Measured from your own check-ins. Nothing here is estimated.
          </p>
        </div>

        <div className="flex gap-1" role="group" aria-label="Reporting window">
          {WINDOWS.map((n) => (
            <button
              key={n}
              className={
                days === n ? "ml-btn-primary ml-btn-sm" : "ml-btn-secondary ml-btn-sm"
              }
              aria-pressed={days === n}
              onClick={() => setDays(n)}
            >
              {n} days
            </button>
          ))}
        </div>
      </div>

      {query.isLoading && (
        <div className="mt-6">
          <TableSkeleton rows={4} />
        </div>
      )}

      {query.isError && (
        <div className="mt-6">
          <ErrorState
            title="Could not load the reports."
            action={
              <button
                className="ml-btn-secondary ml-btn-sm"
                onClick={() => query.refetch()}
              >
                Try again
              </button>
            }
          />
        </div>
      )}

      {query.data && <Body report={query.data} />}
    </div>
  )
}

function Body({ report }: { report: FacilityReport }) {
  return (
    <>
      {/* ----------------------------------------------------------- today */}
      <section className="mt-6">
        <h2 className="ml-label mb-3">Today</h2>
        <div className="grid gap-3 sm:grid-cols-3">
          <Stat label="Checked in" value={report.today.checked_in} />
          <Stat label="Waiting now" value={report.today.waiting} />
          <Stat label="Seen" value={report.today.served} />
        </div>
      </section>

      {/* ------------------------------------------------------------ wait */}
      <section className="mt-8">
        <h2 className="ml-label mb-3">How long people waited</h2>
        <Wait wait={report.wait} />
      </section>

      {/* ---------------------------------------------------- last N days */}
      <section className="mt-8">
        <h2 className="ml-label mb-3">Last {report.days} days</h2>
        <div className="grid gap-3 sm:grid-cols-3">
          <Stat label="Checked in" value={report.period.checked_in} />
          <Stat label="Seen" value={report.period.served} />
          <Stat
            label="Left without being seen"
            value={report.period.left_without_being_seen}
            hint={
              report.period.left_without_being_seen > 0
                ? "People who gave up waiting."
                : undefined
            }
          />
        </div>
      </section>

      {/* --------------------------------------------------- appointments */}
      <section className="mt-8">
        <h2 className="ml-label mb-3">Appointments</h2>
        <div className="grid gap-3 sm:grid-cols-3">
          <Stat label="Booked" value={report.appointments.total} />
          <Stat label="Did not attend" value={report.appointments.no_shows} />
          <Stat
            label="No-show rate"
            value={
              report.appointments.no_show_rate === null
                ? "—"
                : `${Math.round(report.appointments.no_show_rate * 100)}%`
            }
            hint={
              report.appointments.no_show_rate === null
                ? "No appointments booked in this period."
                : undefined
            }
          />
        </div>
      </section>

      {/* --------------------------------------------------------- demand */}
      <section className="mt-8">
        <h2 className="ml-label mb-3">Busiest services</h2>
        {report.demand.length === 0 ? (
          <p className="text-body text-ink-muted">
            No check-ins recorded in this period.
          </p>
        ) : (
          <Demand rows={report.demand} />
        )}
      </section>

      <p className="mt-8 text-caption text-ink-subtle">
        As of{" "}
        {new Date(report.as_of).toLocaleString([], {
          day: "numeric",
          month: "short",
          hour: "2-digit",
          minute: "2-digit",
        })}
        . Counts cover {report.facility} only.
      </p>
    </>
  )
}

function Wait({ wait }: { wait: FacilityReport["wait"] }) {
  if (!wait.enough_data) {
    // No number at all - see the note at the top of this file.
    return (
      <Notice tone="info">
        Not enough visits yet to report a median wait. {wait.sample_size} of the
        10 needed. Keep checking patients in and this fills itself.
      </Notice>
    )
  }

  const change =
    wait.this_week_minutes !== null && wait.last_week_minutes !== null
      ? wait.this_week_minutes - wait.last_week_minutes
      : null

  return (
    <div className="grid gap-3 sm:grid-cols-3">
      <Stat
        label="Median wait"
        value={`${Math.round(wait.median_minutes!)} min`}
        hint={`Across ${wait.sample_size} visits.`}
      />
      <Stat
        label="This week"
        value={
          wait.this_week_minutes === null
            ? "—"
            : `${Math.round(wait.this_week_minutes)} min`
        }
        hint={wait.this_week_minutes === null ? "Too few visits." : undefined}
        // The change belongs on the week it describes, not on the one it is
        // measured against. Direction is never carried by colour alone - the
        // word says it too.
        chip={
          change === null || Math.abs(change) < 1 ? undefined : change < 0 ? (
            <Chip tone="success">
              Down {Math.abs(Math.round(change))} min on last week
            </Chip>
          ) : (
            <Chip tone="warning">
              Up {Math.round(change)} min on last week
            </Chip>
          )
        }
      />
      <Stat
        label="Week before"
        value={
          wait.last_week_minutes === null
            ? "—"
            : `${Math.round(wait.last_week_minutes)} min`
        }
        hint={wait.last_week_minutes === null ? "Too few visits." : undefined}
      />
    </div>
  )
}

function Demand({ rows }: { rows: FacilityReport["demand"] }) {
  const highest = Math.max(...rows.map((r) => r.count), 1)

  return (
    <ul className="space-y-2">
      {rows.map((row) => (
        <li key={row.service}>
          <div className="flex items-baseline justify-between gap-3">
            <span className="text-body">{humanise(row.service)}</span>
            <span className="tabular-nums text-body text-ink-muted">
              {row.count}
            </span>
          </div>
          {/* Illustrative. The count beside it is the fact. */}
          <div
            className="mt-1 h-1.5 overflow-hidden rounded-full bg-surface-sunken"
            role="presentation"
          >
            <span
              className="block h-full rounded-full bg-primary"
              style={{ width: `${Math.round((row.count / highest) * 100)}%` }}
            />
          </div>
        </li>
      ))}
    </ul>
  )
}

function Stat({
  label,
  value,
  hint,
  chip,
}: {
  label: string
  value: string | number
  hint?: string
  chip?: React.ReactNode
}) {
  return (
    <div className="rounded-lg border border-line bg-surface p-4">
      <p className="ml-label">{label}</p>
      <p className="mt-1 text-h2 tabular-nums">{value}</p>
      {chip && <div className="mt-2">{chip}</div>}
      {hint && <p className="mt-1 text-caption text-ink-subtle">{hint}</p>}
    </div>
  )
}

function humanise(code: string) {
  return code.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase())
}
