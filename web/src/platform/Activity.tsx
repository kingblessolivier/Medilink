import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { api } from "../api/client"
import {
  Chip,
  EmptyState,
  ErrorState,
  Notice,
  StatCard,
  TableSkeleton,
} from "../ui"
import {
  IconAlert,
  IconBell,
  IconCalendar,
  IconClock,
  IconHospital,
  IconUsers,
} from "../ui/icons"

/**
 * What is happening right now, across every facility.
 *
 * Counts and status, never people. An administrator needs to know that
 * Kimironko has eleven waiting and Remera has none; they do not need to know
 * who those eleven are, and there is no endpoint here that would tell them.
 *
 * Two numbers earn their place by being uncomfortable:
 *
 *   facilities_active   verified, staffed, and nobody has ever been checked
 *                       in - a facility onboarded on paper only
 *   delivery failures   a "leave now" SMS that never sent is a patient still
 *                       sitting at home
 */

const WINDOWS = [7, 30, 90] as const

const KIND: Record<string, string> = {
  otp: "Sign-in codes",
  called: "Called to a room",
  leave_now: "Time to leave",
  appt_reminder_2h: "Appointment reminder",
  appt_confirmed: "Booking confirmed",
  appt_cancelled: "Booking cancelled",
}

export function PlatformActivity() {
  const [days, setDays] = useState<number>(7)

  const activity = useQuery({
    queryKey: ["admin", "activity", days],
    queryFn: () => api.adminActivity(days),
    // The waiting counts are live numbers; a stale board is misleading.
    refetchInterval: 60_000,
    staleTime: 30_000,
  })

  const delivery = useQuery({
    queryKey: ["admin", "delivery", days],
    queryFn: () => api.adminDelivery(days),
    staleTime: 60_000,
  })

  const totals = activity.data?.totals
  const facilities = activity.data?.facilities ?? []
  const idle = facilities.filter(
    (f) => !f.waiting && !f.seen && !f.booked,
  ).length

  return (
    <div className="mx-auto w-full max-w-6xl">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-h2">Activity</h1>
          <p className="mt-1 text-body text-n700">
            Across every facility. Counts only — no patient is named here.
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

      {activity.isError && (
        <div className="mt-5">
          <ErrorState
            title="Could not load platform activity."
            action={
              <button
                className="ml-btn-secondary ml-btn-sm"
                onClick={() => activity.refetch()}
              >
                Try again
              </button>
            }
          />
        </div>
      )}

      {/* --------------------------------------------------------- now */}
      <section className="ml-section">
        <h2 className="text-h3 mb-4">Right now</h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            label="Waiting"
            value={totals?.waiting_now ?? "—"}
            icon={<IconUsers size={18} />}
            tone="primary"
            hint="People in a queue at this moment."
          />
          <StatCard
            label={`Seen, ${days} days`}
            value={totals?.seen ?? "—"}
            icon={<IconClock size={18} />}
          />
          <StatCard
            label={`Booked, ${days} days`}
            value={totals?.booked ?? "—"}
            icon={<IconCalendar size={18} />}
          />
          <StatCard
            label="Did not attend"
            value={totals?.no_shows ?? "—"}
            icon={<IconAlert size={18} />}
            tone={totals?.no_shows ? "warning" : "neutral"}
          />
        </div>

        {idle > 0 && (
          <div className="mt-4">
            {/* Onboarded on paper only. Invisible from every other screen. */}
            <Notice tone="warning">
              {idle} verified {idle === 1 ? "facility has" : "facilities have"}{" "}
              had no check-ins, no bookings and nobody waiting in this period.
            </Notice>
          </div>
        )}
      </section>

      {/* -------------------------------------------------- by facility */}
      <section className="ml-section">
        <h2 className="text-h3 mb-4">By facility</h2>

        {activity.isLoading && <TableSkeleton rows={6} />}

        {activity.isSuccess && facilities.length === 0 && (
          <EmptyState
            icon={<IconHospital size={20} />}
            title="No verified facilities yet."
            body="Verify a facility and it will appear here."
          />
        )}

        {facilities.length > 0 && (
          <div className="ml-scroll-x rounded-lg border border-n200 bg-white">
            <table className="ml-table">
              <thead>
                <tr>
                  <th scope="col">Facility</th>
                  <th scope="col">District</th>
                  <th scope="col">Waiting</th>
                  <th scope="col">Seen</th>
                  <th scope="col">Booked</th>
                  <th scope="col">Wait times</th>
                </tr>
              </thead>
              <tbody>
                {facilities.map((f) => (
                  <tr key={f.name}>
                    <td className="font-medium">{f.name}</td>
                    <td className="text-n700">{f.district}</td>
                    <td className="tabular-nums">
                      {f.waiting > 0 ? (
                        <Chip tone="warning">{f.waiting}</Chip>
                      ) : (
                        <span className="text-n600">0</span>
                      )}
                    </td>
                    <td className="tabular-nums">{f.seen}</td>
                    <td className="tabular-nums">{f.booked}</td>
                    <td>
                      {f.reports_queue ? (
                        <Chip tone="success">Published</Chip>
                      ) : (
                        <span className="text-body text-n600">
                          Not reported
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* ---------------------------------------------------- messages */}
      <section className="ml-section">
        <h2 className="text-h3 mb-1">Messages</h2>
        <p className="mb-4 max-w-prose text-body text-n700">
          A &ldquo;time to leave&rdquo; message that never sent is a patient
          still sitting at home.
        </p>

        <div className="grid gap-3 sm:grid-cols-3">
          <StatCard
            label="Sent"
            value={delivery.data?.sent ?? "—"}
            icon={<IconBell size={18} />}
          />
          <StatCard
            label="Failed"
            value={delivery.data?.failed ?? "—"}
            icon={<IconAlert size={18} />}
            tone={delivery.data?.failed ? "danger" : "neutral"}
          />
          <StatCard
            label="Failure rate"
            value={
              delivery.data?.failure_rate === null ||
              delivery.data?.failure_rate === undefined
                ? "—"
                : `${Math.round(delivery.data.failure_rate * 100)}%`
            }
            icon={<IconAlert size={18} />}
            // Null, not 0%. No messages is not a perfect record.
            hint={
              delivery.data && delivery.data.total === 0
                ? "No messages in this period."
                : undefined
            }
          />
        </div>

        {(delivery.data?.by_kind.length ?? 0) > 0 && (
          <div className="mt-4 ml-scroll-x rounded-lg border border-n200 bg-white">
            <table className="ml-table">
              <thead>
                <tr>
                  <th scope="col">Kind</th>
                  <th scope="col">Sent</th>
                  <th scope="col">Failed</th>
                </tr>
              </thead>
              <tbody>
                {delivery.data!.by_kind.map((k) => (
                  <tr key={k.kind}>
                    <td>{KIND[k.kind] ?? k.kind}</td>
                    <td className="tabular-nums">{k.sent}</td>
                    <td className="tabular-nums">
                      {k.failed > 0 ? (
                        <Chip tone="danger">{k.failed}</Chip>
                      ) : (
                        <span className="text-n600">0</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <p className="mt-3 text-label text-n600">
          Message contents are never shown. Several carry a queue position and
          one carries a sign-in code.
        </p>
      </section>
    </div>
  )
}
