import { useState } from "react"
import { Link } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { api, type AdminOverview } from "../api/client"
import { ErrorState, Notice, Skeleton } from "../ui"

/**
 * Is the platform being used, and what is blocking it?
 *
 * Counts only. There is no patient list here and no endpoint to build one
 * from - the backend exposes a patient COUNT and nothing else, because an
 * endpoint that returns patients is one somebody will eventually search.
 *
 * The verification backlog is given the most weight on the screen. An
 * unverified facility is invisible to patients, so a backlog is not tidy-up
 * work - it is people unable to find care that exists.
 */

const WINDOWS = [7, 30, 90] as const

const CHANNEL_LABEL: Record<string, string> = {
  app: "App",
  ussd: "USSD",
  whatsapp: "WhatsApp",
  desk: "Reception desk",
}

export function Overview() {
  const [days, setDays] = useState<number>(30)

  const query = useQuery({
    queryKey: ["overview", days],
    queryFn: () => api.overview(days),
  })

  return (
    <div className="mx-auto w-full max-w-5xl">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-h2">Overview</h1>
          <p className="mt-1 text-small text-ink-muted">
            Counts across every facility. No patient records are shown here.
          </p>
        </div>

        <div className="flex gap-1" role="group" aria-label="Reporting window">
          {WINDOWS.map((n) => (
            <button
              key={n}
              className={
                days === n
                  ? "ml-btn-primary ml-btn-sm"
                  : "ml-btn-secondary ml-btn-sm"
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
        <div className="mt-6 grid gap-3 sm:grid-cols-3">
          {Array.from({ length: 6 }, (_, i) => (
            <div key={i} className="rounded-lg border border-line bg-surface p-4">
              <Skeleton className="h-3 w-24" />
              <Skeleton className="mt-3 h-6 w-16" />
            </div>
          ))}
        </div>
      )}

      {query.isError && (
        <div className="mt-6">
          <ErrorState
            title="Could not load the overview."
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

      {query.data && <Body data={query.data} />}
    </div>
  )
}

function Body({ data }: { data: AdminOverview }) {
  const backlog =
    data.facilities.awaiting_verification + data.providers.awaiting_verification

  return (
    <>
      {backlog > 0 && (
        <div className="mt-5">
          {/* The one thing on this screen that is an action rather than a
              number: an unverified facility cannot be found by a patient. */}
          <Notice tone="warning">
            {data.facilities.awaiting_verification} facilities and{" "}
            {data.providers.awaiting_verification} doctors are waiting to be
            verified. Until they are, patients cannot find them.{" "}
            <Link to="/verification" className="underline">
              Open the verification queue
            </Link>
          </Notice>
        </div>
      )}

      <section className="mt-8">
        <h2 className="ml-label mb-3">Facilities</h2>
        <div className="grid gap-3 sm:grid-cols-4">
          <Stat label="Listed" value={data.facilities.total} />
          <Stat label="Verified" value={data.facilities.verified} />
          <Stat
            label="Awaiting verification"
            value={data.facilities.awaiting_verification}
          />
          <Stat
            label="Reporting queue"
            value={data.facilities.reporting_queue}
            hint="Facilities publishing live wait times."
          />
        </div>
      </section>

      <section className="mt-8">
        <h2 className="ml-label mb-3">Doctors</h2>
        <div className="grid gap-3 sm:grid-cols-3">
          <Stat label="Listed" value={data.providers.total} />
          <Stat label="Verified" value={data.providers.verified} />
          <Stat
            label="Awaiting verification"
            value={data.providers.awaiting_verification}
          />
        </div>
      </section>

      <section className="mt-8">
        <h2 className="ml-label mb-3">Last {data.days} days</h2>
        <div className="grid gap-3 sm:grid-cols-3">
          <Stat label="Check-ins" value={data.activity.check_ins} />
          <Stat label="Appointments" value={data.activity.appointments} />
          <Stat
            label="Registered patients"
            value={data.patients.registered}
            hint="A count. Patient records are not reachable from this portal."
          />
        </div>
      </section>

      <section className="mt-8">
        <h2 className="ml-label mb-3">How people booked</h2>
        {data.activity.by_channel.length === 0 ? (
          <p className="text-body text-ink-muted">
            No appointments booked in this period.
          </p>
        ) : (
          <Channels rows={data.activity.by_channel} />
        )}
      </section>

      <p className="mt-8 text-caption text-ink-subtle">
        As of{" "}
        {new Date(data.as_of).toLocaleString([], {
          day: "numeric",
          month: "short",
          hour: "2-digit",
          minute: "2-digit",
        })}
        .
      </p>
    </>
  )
}

function Channels({ rows }: { rows: AdminOverview["activity"]["by_channel"] }) {
  const highest = Math.max(...rows.map((r) => r.count), 1)

  return (
    <ul className="space-y-2">
      {rows.map((row) => (
        <li key={row.channel}>
          <div className="flex items-baseline justify-between gap-3">
            <span className="text-body">
              {CHANNEL_LABEL[row.channel] ?? row.channel}
            </span>
            <span className="tabular-nums text-body text-ink-muted">
              {row.count}
            </span>
          </div>
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
}: {
  label: string
  value: string | number
  hint?: string
}) {
  return (
    <div className="rounded-lg border border-line bg-surface p-4">
      <p className="ml-label">{label}</p>
      <p className="mt-1 text-h2 tabular-nums">{value}</p>
      {hint && <p className="mt-1 text-caption text-ink-subtle">{hint}</p>}
    </div>
  )
}
