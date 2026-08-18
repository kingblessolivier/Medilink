import { useQuery } from "@tanstack/react-query"
import { Link, useParams } from "react-router-dom"
import { api } from "../api/client"
import { useI18n } from "../i18n"
import { WaitLine } from "../components/WaitLine"

const WEEKDAYS = [0, 1, 2, 3, 4, 5, 6]

export function FacilityDetail() {
  const { slug = "" } = useParams()
  const { t, lang } = useI18n()

  const { data, isLoading, isError } = useQuery({
    queryKey: ["facility", slug],
    queryFn: () => api.facility(slug),
    staleTime: 5 * 60_000,
  })

  if (isLoading) {
    return <p className="p-4 text-sm text-neutral-500">{t("loading")}</p>
  }
  if (isError || !data) {
    return <p className="p-4 text-sm text-danger">{t("error_generic")}</p>
  }

  const byWeekday = new Map<number, string[]>()
  for (const hours of data.opening_hours) {
    const periods = byWeekday.get(hours.weekday) ?? []
    periods.push(hours.opens_at + " - " + hours.closes_at)
    byWeekday.set(hours.weekday, periods)
  }

  return (
    <div className="mx-auto max-w-md px-4 pb-24 pt-4">
      <Link to="/" className="text-sm text-primary">
        {t("back")}
      </Link>

      <h1 className="mt-2 text-xl font-semibold">{data.name}</h1>
      <p className="text-sm text-neutral-500">
        {data.sector}, {data.district}
      </p>

      <div className="mt-2">
        <WaitLine wait={data.wait} />
      </div>

      <div className="mt-4 flex gap-2">
        <a
          className="btn-primary flex-1"
          href={data.directions_url}
          target="_blank"
          rel="noreferrer"
        >
          {t("directions")}
        </a>
        {data.phone && (
          <a className="btn-secondary flex-1" href={"tel:" + data.phone}>
            {t("call")}
          </a>
        )}
      </div>

      <section className="card mt-5">
        <h2 className="mb-2 font-semibold">{t("insurers_accepted")}</h2>
        <ul className="text-sm">
          {data.insurers.map((i) => (
            <li key={i.code} className="py-0.5">
              {i.name}
              {i.note && <span className="text-neutral-500"> - {i.note}</span>}
            </li>
          ))}
        </ul>
      </section>

      <section className="card mt-3">
        <h2 className="mb-2 font-semibold">{t("services_offered")}</h2>
        <ul className="text-sm">
          {data.services.map((s) => (
            <li key={s.code} className="py-0.5">
              {lang === "rw" ? s.name_rw : lang === "fr" ? s.name_fr : s.name_en}
            </li>
          ))}
        </ul>
      </section>

      <section className="card mt-3">
        <h2 className="mb-2 font-semibold">{t("opening_hours")}</h2>
        <ul className="text-sm">
          {WEEKDAYS.map((weekday) => (
            <li key={weekday} className="flex justify-between py-0.5">
              <span>{t("weekday_" + weekday)}</span>
              <span className="text-neutral-600">
                {byWeekday.get(weekday)?.join(", ") ?? t("closed")}
              </span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
