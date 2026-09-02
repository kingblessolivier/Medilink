import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { api } from "../api/client"
import {
  BarRow,
  Chip,
  EmptyState,
  ErrorState,
  Notice,
  StatCard,
  TableSkeleton,
} from "../ui"
import { IconShield, IconUser, IconUsers } from "../ui/icons"

/**
 * Who can read patient records, and who has been reading them.
 *
 * Two halves of one question, which is why they share a screen:
 *
 *   WHO CAN   the staff accounts, and which facility each one opens
 *   WHO DID   the access log, grouped by actor
 *
 * docs/08 section 6 built the log "to surface the anomaly that matters - a
 * receptionist viewing hundreds of records outside their shift". It was
 * written to the database from the first release and read by nobody. An audit
 * trail nobody looks at is a log file, not a control.
 *
 * The patient is never named. Who did the touching, how much and when is what
 * an access review needs; naming the patient would make the oversight tool
 * its own disclosure risk.
 */

const ROLE: Record<string, string> = {
  receptionist: "Receptionist",
  admin: "Facility administrator",
  clinician: "Clinician",
}

const WINDOWS = [7, 30, 90] as const

export function PlatformAccess() {
  const [days, setDays] = useState<number>(7)

  const staff = useQuery({
    queryKey: ["admin", "staff"],
    queryFn: api.adminStaff,
    staleTime: 60_000,
  })

  const log = useQuery({
    queryKey: ["admin", "access-log", days],
    queryFn: () => api.adminAccessLog(days),
    staleTime: 30_000,
  })

  const rows = staff.data?.results ?? []
  const inactive = rows.filter((s) => !s.active).length
  const busiest = Math.max(
    ...(log.data?.by_actor.map((a) => a.events) ?? [1]),
    1,
  )

  return (
    <div className="mx-auto w-full max-w-6xl">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-h2">Access</h1>
          <p className="mt-1 text-body text-n700">
            Who can read patient records, and who has been.
          </p>
        </div>

        <div className="flex gap-1" role="group" aria-label="Reporting window">
          {WINDOWS.map((n) => (
            <button
              key={n}
              aria-pressed={days === n}
              className={
                days === n
                  ? "ml-btn-primary ml-btn-sm"
                  : "ml-btn-secondary ml-btn-sm"
              }
              onClick={() => setDays(n)}
            >
              {n} days
            </button>
          ))}
        </div>
      </div>

      {/* ------------------------------------------------------ summary */}
      <section className="ml-section">
        <div className="grid gap-3 sm:grid-cols-3">
          <StatCard
            label="Staff accounts"
            value={rows.length}
            icon={<IconUsers size={18} />}
            hint={
              inactive > 0 ? `${inactive} deactivated.` : "All active."
            }
          />
          <StatCard
            label={`Access events, ${days} days`}
            value={log.data?.total_events ?? "—"}
            icon={<IconShield size={18} />}
            tone="primary"
          />
          <StatCard
            label="Accounts with no surface"
            value={staff.data?.accounts.stranded ?? "—"}
            icon={<IconUser size={18} />}
            hint="Can sign in, and land nowhere."
            tone={
              (staff.data?.accounts.stranded ?? 0) > 0 ? "warning" : "neutral"
            }
          />
        </div>
      </section>

      {/* --------------------------------------------------- who can read */}
      <section className="ml-section">
        <h2 className="text-h3 mb-1">Who can read patient records</h2>
        <p className="mb-4 max-w-prose text-body text-n700">
          Each account below opens exactly one facility's patient data. A
          dormant account left active is a standing door.
        </p>

        {staff.isLoading && <TableSkeleton rows={4} />}
        {staff.isError && (
          <ErrorState
            title="Could not load staff accounts."
            action={
              <button
                className="ml-btn-secondary ml-btn-sm"
                onClick={() => staff.refetch()}
              >
                Try again
              </button>
            }
          />
        )}

        {rows.length > 0 && (
          <div className="ml-scroll-x rounded-lg border border-n200 bg-white">
            <table className="ml-table">
              <thead>
                <tr>
                  <th scope="col">Account</th>
                  <th scope="col">Facility</th>
                  <th scope="col">Role</th>
                  <th scope="col">Can change the queue</th>
                  <th scope="col">Last signed in</th>
                  <th scope="col">Status</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((s) => (
                  <tr key={s.id}>
                    <td className="font-medium">{s.username}</td>
                    <td className="text-n700">{s.facility}</td>
                    <td className="text-n700">{ROLE[s.role] ?? s.role}</td>
                    <td>
                      {s.can_manage_queue ? (
                        <Chip tone="neutral">Yes</Chip>
                      ) : (
                        <span className="text-body text-n600">
                          Read only
                        </span>
                      )}
                    </td>
                    <td className="tabular-nums text-n700">
                      {s.last_login
                        ? new Date(s.last_login).toLocaleDateString(undefined, {
                            day: "numeric",
                            month: "short",
                            year: "numeric",
                          })
                        : "Never"}
                    </td>
                    <td>
                      {s.active ? (
                        <Chip tone="success">Active</Chip>
                      ) : (
                        <Chip tone="unknown">Deactivated</Chip>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* --------------------------------------------------- who has read */}
      <section className="ml-section">
        <h2 className="text-h3 mb-1">Who has been reading them</h2>
        <p className="mb-4 max-w-prose text-body text-n700">
          Grouped by account. One &ldquo;viewed 20 records&rdquo; event is a
          queue board; forty of them from one account is something to ask
          about.
        </p>

        {log.isLoading && <TableSkeleton rows={4} />}

        {log.data?.by_actor.length === 0 && (
          <EmptyState
            icon={<IconShield size={20} />}
            title="No recorded access in this period."
            body="Nobody opened a patient record at any facility."
          />
        )}

        {(log.data?.by_actor.length ?? 0) > 0 && (
          <ul className="max-w-2xl space-y-3">
            {log.data!.by_actor.map((a) => (
              <BarRow
                key={`${a.actor}-${a.facility}`}
                label={`${a.actor} · ${a.facility}`}
                count={a.events}
                max={busiest}
              />
            ))}
          </ul>
        )}
      </section>

      {/* -------------------------------------------------------- recent */}
      {(log.data?.recent.length ?? 0) > 0 && (
        <section className="ml-section">
          <h2 className="text-h3 mb-1">Most recent</h2>
          <p className="mb-4 text-body text-n700">
            The latest {log.data!.recent.length} of {log.data!.total_events}{" "}
            events in this period. The grouped totals above are where a spike
            shows up; this is for checking what one was made of.
          </p>
          <div className="ml-scroll-x rounded-lg border border-n200 bg-white">
            <table className="ml-table">
              <thead>
                <tr>
                  <th scope="col">When</th>
                  <th scope="col">Account</th>
                  <th scope="col">Action</th>
                  <th scope="col">Facility</th>
                  <th scope="col">Records</th>
                  <th scope="col">From</th>
                </tr>
              </thead>
              <tbody>
                {log.data!.recent.map((e) => (
                  <tr key={e.id}>
                    <td className="whitespace-nowrap tabular-nums text-n700">
                      {new Date(e.occurred_at).toLocaleString(undefined, {
                        day: "numeric",
                        month: "short",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </td>
                    <td className="font-medium">{e.actor}</td>
                    <td className="text-n700">{e.action_label}</td>
                    <td className="text-n700">{e.facility}</td>
                    <td className="tabular-nums">{e.record_count}</td>
                    <td className="tabular-nums text-n600">
                      {e.ip_address ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="mt-4">
            <Notice tone="info">
              Patients are deliberately not named here. An access review needs
              to know who did the reading, not whose record was read.
            </Notice>
          </div>
        </section>
      )}
    </div>
  )
}
