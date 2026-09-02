/**
 * FA-01, the facility dashboard, per docs/02_dashboards.html.
 *
 * The workspace had no overview at all: an administrator signing in landed on
 * the reception desk, which is a receptionist's screen, and had to read the
 * reports page to learn how the day was going.
 *
 * WHAT THE MOCK DRAWS THAT THIS DOES NOT, and why:
 *
 * - "^12 vs yesterday", "-8 min vs last week" on the tiles. /staff/reports
 *   returns no day-over-day comparison, and the only week-over-week figures
 *   it carries are wait medians that come back null until there is enough
 *   history. A delta is a claim about a trend; inventing one on a health
 *   service is the same failure as inventing a wait time.
 *
 * - The hourly patient flow line. There is no hourly series in the API - the
 *   report is daily totals - and a line drawn through four points a client
 *   made up is worse than no line.
 *
 * - The department donut. Deliberately a sorted bar list instead. Six of the
 *   seven services sit within a few visits of each other, and a donut is the
 *   one form that cannot show close values: the eye compares angles it cannot
 *   measure. Same data, one hue, ordered - which is also what the rest of this
 *   product already uses for demand.
 *
 * THE WAIT TILE OBEYS `enough_data`. It shows a median only when the backend
 * says the sample supports one, and says so plainly when it does not. That is
 * the same gate the patient app uses, and an administrator reading a made-up
 * median would go on to quote it.
 */

import { useQuery } from "@tanstack/react-query"
import { api, type FacilityReport } from "../api/client"
import { useI18n } from "../i18n"
import { useServiceTypes } from "../hooks/useNearbyFacilities"
import { BarRow, ErrorState, StatCard, TableSkeleton } from "../ui"
import { IconCalendar, IconCheck, IconClock, IconAlert } from "../ui/icons"

export function WorkspaceDashboard() {
  const { t, lang } = useI18n()
  const serviceTypes = useServiceTypes()

  const report = useQuery<FacilityReport>({
    queryKey: ["staff", "reports"],
    queryFn: () => api.staffReports(),
    staleTime: 60_000,
  })

  if (report.isLoading) return <TableSkeleton rows={4} />
  if (report.isError || !report.data) {
    return <ErrorState title={t("error_generic")} />
  }

  const r = report.data
  const demand = r.demand ?? []
  const busiest = Math.max(1, ...demand.map((d) => d.count))

  /** Service codes are not labels. Resolve them, and fall back to the code. */
  const serviceLabel = (code: string) => {
    const match = serviceTypes.data?.results.find((s) => s.code === code)
    if (!match) return code
    return lang === "rw"
      ? match.name_rw
      : lang === "fr"
        ? match.name_fr
        : match.name_en
  }

  /* Nullable in the schema, and the type checker was right to insist: the
     rate is null when there are no appointments to divide by. A facility with
     an empty book would otherwise read "NaN%", or worse, "0% no-shows" -
     which sounds like a good day rather than no data. */
  const noShowRate =
    r.appointments.no_show_rate === null
      ? null
      : `${Math.round(r.appointments.no_show_rate * 100)}%`

  return (
    <div>
      <h1 className="text-h1 text-n900">{t("ws_today_overview")}</h1>
      <p className="mt-1 text-body text-n700">
        {t("ws_report_window", { days: r.days })}
      </p>

      {/* The four numbers an administrator opens this page for. */}
      <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label={t("ws_kpi_appointments")}
          value={r.appointments.total}
          icon={<IconCalendar size={18} />}
          tone="primary"
        />
        <StatCard
          label={t("ws_kpi_attended")}
          value={r.period.served}
          hint={t("ws_kpi_attended_hint", { n: r.period.checked_in })}
          icon={<IconCheck size={18} />}
        />
        <StatCard
          label={t("ws_kpi_no_shows")}
          value={r.appointments.no_shows}
          hint={noShowRate ? t("ws_kpi_no_show_rate", { rate: noShowRate }) : undefined}
          icon={<IconAlert size={18} />}
          // Tinted only when there is something to look at. A red plate on a
          // facility with one no-show is an accusation, not information.
          tone={
            r.appointments.no_show_rate !== null &&
            r.appointments.no_show_rate >= 0.15
              ? "warning"
              : "neutral"
          }
        />
        <StatCard
          label={t("ws_kpi_wait")}
          // An em dash, not a zero: `value` takes a string precisely so a
          // screen can say "we do not know" without inventing a number.
          value={
            r.wait.enough_data && r.wait.median_minutes !== null
              ? t("ws_minutes", { n: Math.round(r.wait.median_minutes) })
              : "—"
          }
          hint={
            r.wait.enough_data
              ? t("ws_kpi_wait_hint", { n: r.wait.sample_size })
              : t("ws_kpi_wait_insufficient")
          }
          icon={<IconClock size={18} />}
        />
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        {/* Right now, at the desk. */}
        <div className="ml-card p-4">
          <h2 className="ml-label">{t("ws_today_now")}</h2>
          <dl className="mt-3 grid grid-cols-3 gap-3 text-center">
            {[
              ["ws_today_checked_in", r.today.checked_in],
              ["ws_today_waiting", r.today.waiting],
              ["ws_today_served", r.today.served],
            ].map(([key, value]) => (
              <div key={key as string} className="rounded-md bg-n100 p-3">
                <dt className="text-label text-n600">{t(key as string)}</dt>
                <dd className="mt-1 text-h2 tabular-nums text-n900">{value}</dd>
              </div>
            ))}
          </dl>
        </div>

        {/* Demand by service. One hue, ordered - see the note above on why
            this is not the donut the mock draws. */}
        <div className="ml-card p-4">
          <h2 className="ml-label">{t("ws_by_department")}</h2>
          {demand.length === 0 ? (
            <p className="mt-3 text-body text-n700">{t("ws_no_demand")}</p>
          ) : (
            <ul className="mt-3 space-y-3">
              {[...demand]
                .sort((a, b) => b.count - a.count)
                .map((row) => (
                  <BarRow
                    key={row.service}
                    label={serviceLabel(row.service)}
                    count={row.count}
                    max={busiest}
                  />
                ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}

export default WorkspaceDashboard
