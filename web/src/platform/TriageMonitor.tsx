import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { api, type TriageMonitoring } from "../api/client"
import { BarRow, ErrorState, Notice, Skeleton, StatCard } from "../ui"
import { IconAlert, IconHeart } from "../ui/icons"

/**
 * Care Guide monitoring.
 *
 * Reads `TriageOutcome` and nothing else. That model has no patient link, no
 * session id and no answers, and buckets by hour rather than timestamp so a
 * row cannot be correlated with a queue check-in a minute later. Everything on
 * this screen is a count over that table.
 *
 * The question it exists to answer: does this protocol send too many people to
 * an emergency department? A protocol escalating a quarter of its sessions is
 * either seeing a genuinely sick population or is broken, and a clinician
 * needs to know which. It is not a screen for looking at what anyone said.
 */

const WINDOWS = [7, 30, 90] as const

export function TriageMonitor() {
  const [days, setDays] = useState<number>(30)

  const query = useQuery({
    queryKey: ["triage-monitoring", days],
    queryFn: () => api.triageMonitoring(days),
  })

  return (
    <div className="mx-auto w-full max-w-4xl">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-h2">Care Guide monitoring</h1>
          <p className="mt-1 text-small text-ink-muted">
            Anonymous outcomes only. Answers are never stored.
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
          {Array.from({ length: 3 }, (_, i) => (
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
            title="Could not load monitoring."
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

function Body({ data }: { data: TriageMonitoring }) {
  if (data.sessions === 0) {
    return (
      <div className="mt-6">
        {/* The expected state today: the clinical gate is shut, so nothing has
            run. Saying that is more useful than three zeroes. */}
        <Notice tone="info">
          No Care Guide sessions in this period. The clinical gate is shut until
          a licensed clinician signs off a protocol, so this stays empty until
          then.
        </Notice>
      </div>
    )
  }

  return (
    <>
      <section className="mt-6">
        <div className="grid gap-3 sm:grid-cols-3">
          <StatCard label="Sessions" value={data.sessions} icon={<IconHeart size={18} />} />
          <StatCard label="Escalated to emergency" value={data.escalations} icon={<IconAlert size={18} />} tone="danger" />
          <StatCard
            label="Escalation rate"
            value={
              data.escalation_rate === null
                ? "—"
                : `${Math.round(data.escalation_rate * 100)}%`
            }
            hint={
              data.escalation_rate === null
                ? `Needs ${data.minimum_sessions} sessions. ${data.sessions} so far.`
                : undefined
            }
          />
        </div>
      </section>

      {!data.enough_data && (
        <div className="mt-4">
          {/* No rate printed at all under the floor. Somebody will tune a
              clinical protocol on whatever number is on this screen. */}
          <Notice tone="info">
            Not enough sessions to report a rate yet. A protocol should not be
            adjusted on fewer than {data.minimum_sessions}.
          </Notice>
        </div>
      )}

      <section className="mt-8">
        <h2 className="text-h3 mb-3">Where sessions were sent</h2>
        {data.by_service.length === 0 ? (
          <p className="text-body text-ink-muted">
            No service recommendations in this period.
          </p>
        ) : (
          <Bars
            rows={data.by_service.map((r) => ({
              label: humanise(r.service),
              count: r.count,
            }))}
          />
        )}
      </section>

      <section className="mt-8">
        <h2 className="text-h3 mb-3">By protocol version</h2>
        <p className="mb-3 text-small text-ink-muted">
          A rule change has to be traceable to what it did to these numbers.
        </p>
        <div className="overflow-x-auto rounded-lg border border-line bg-surface">
          <table className="ml-table">
            <thead>
              <tr>
                <th scope="col">Version</th>
                <th scope="col">Sessions</th>
                <th scope="col">Escalations</th>
                <th scope="col">Rate</th>
              </tr>
            </thead>
            <tbody>
              {data.by_version.map((row) => (
                <tr key={row.protocol_version}>
                  <td className="font-mono">{row.protocol_version}</td>
                  <td className="tabular-nums">{row.sessions}</td>
                  <td className="tabular-nums">{row.escalations}</td>
                  <td className="tabular-nums text-ink-muted">
                    {/* Per-version rates are held to the same floor as the
                        headline one. */}
                    {row.sessions >= data.minimum_sessions
                      ? `${Math.round((row.escalations / row.sessions) * 100)}%`
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <p className="mt-8 text-caption text-ink-subtle">
        Outcomes carry no patient, no session and no answers, and are bucketed
        by hour so a row cannot be matched to a visit.
      </p>
    </>
  )
}

function Bars({ rows }: { rows: { label: string; count: number }[] }) {
  const highest = Math.max(...rows.map((r) => r.count), 1)
  return (
    <ul className="max-w-2xl space-y-3">
      {rows.map((row) => (
        <BarRow key={row.label} label={row.label} count={row.count} max={highest} />
      ))}
    </ul>
  )
}


function humanise(code: string) {
  return code.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase())
}
