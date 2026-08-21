import { useSearchParams } from "react-router-dom"
import { useI18n } from "../i18n"
import { useProviders } from "../hooks/useProviders"
import { useSpecialties } from "../hooks/useSpecialties"
import { useDistricts } from "../hooks/useNearbyFacilities"
import { DoctorCard } from "../components/DoctorCard"
import {
  Button,
  EmptyState,
  ErrorState,
  Field,
  ListSkeleton,
  Notice,
  Select,
  TextInput,
} from "../ui"

const LANGUAGES = [
  ["rw", "Kinyarwanda"],
  ["en", "English"],
  ["fr", "Francais"],
  ["sw", "Kiswahili"],
] as const

/**
 * The doctors directory.
 *
 * Language is a first-class filter, not an afterthought. A patient who is only
 * comfortable in Kinyarwanda needs to know which clinician can consult in it
 * before they travel, and that is exactly the kind of thing a directory can
 * answer and a phone call cannot.
 *
 * Filters live in the URL so a result can be shared - "here is the paediatrician
 * who speaks French" is a message somebody sends to a relative.
 */
export function Doctors() {
  const { t, lang } = useI18n()
  const [params, setParams] = useSearchParams()

  const specialty = params.get("specialty") ?? undefined
  const language = params.get("language") ?? undefined
  const search = params.get("q") ?? undefined

  const { data: specialtyData } = useSpecialties()
  useDistricts() // warmed for the facility links below
  const query = useProviders({ specialty, language, search, limit: 30 })

  function setParam(key: string, value: string | undefined) {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next, { replace: true })
  }

  const specialtyLabel = (s: {
    name_rw: string
    name_en: string
    name_fr: string
  }) => (lang === "rw" ? s.name_rw : lang === "fr" ? s.name_fr : s.name_en)

  const results = query.data?.results ?? []

  return (
    <div className="ml-page py-6 pb-24">
      <h1 className="text-h1">{t("doctors_title")}</h1>
      <p className="mt-1 max-w-prose text-body text-ink-muted">
        {t("doctors_body")}
      </p>

      <div className="ml-card mt-5 grid gap-3 p-4 sm:grid-cols-3">
        <Field label={t("search_by_name")}>
          {(id) => (
            <TextInput
              id={id}
              type="search"
              defaultValue={search ?? ""}
              placeholder={t("search_by_name")}
              onChange={(e) => setParam("q", e.target.value || undefined)}
            />
          )}
        </Field>

        <Field label={t("group_specialties")}>
          {(id) => (
            <Select
              id={id}
              value={specialty ?? ""}
              onChange={(e) => setParam("specialty", e.target.value || undefined)}
            >
              <option value="">{t("all_specialties")}</option>
              {(specialtyData?.results ?? []).map((s) => (
                <option key={s.code} value={s.code}>
                  {specialtyLabel(s)}
                </option>
              ))}
            </Select>
          )}
        </Field>

        <Field label={t("language_spoken")}>
          {(id) => (
            <Select
              id={id}
              value={language ?? ""}
              onChange={(e) => setParam("language", e.target.value || undefined)}
            >
              <option value="">{t("any_language")}</option>
              {LANGUAGES.map(([code, name]) => (
                <option key={code} value={code}>
                  {name}
                </option>
              ))}
            </Select>
          )}
        </Field>
      </div>

      <div className="mb-3 mt-5 flex items-baseline justify-between">
        <p className="ml-label">
          {query.data ? t("n_results", { n: query.data.count }) : " "}
        </p>
        {(specialty || language || search) && (
          <Button
            size="sm"
            variant="tertiary"
            onClick={() => setParams(new URLSearchParams(), { replace: true })}
          >
            {t("clear_filters")}
          </Button>
        )}
      </div>

      {query.isLoading && <ListSkeleton rows={4} />}

      {query.isError && (
        <ErrorState
          title={t("error_generic")}
          action={
            <Button size="sm" onClick={() => query.refetch()}>
              {t("retry")}
            </Button>
          }
        />
      )}

      {query.data && results.length === 0 && (
        <EmptyState
          title={t("no_doctors_found")}
          body={t("no_doctors_found_body")}
          action={
            <Button
              size="sm"
              onClick={() => setParams(new URLSearchParams(), { replace: true })}
            >
              {t("clear_filters")}
            </Button>
          }
        />
      )}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {results.map((doctor) => (
          <DoctorCard key={doctor.slug} doctor={doctor} />
        ))}
      </div>

      {results.length > 0 && (
        <div className="mt-5">
          <Notice tone="info">{t("doctors_verification_note")}</Notice>
        </div>
      )}
    </div>
  )
}
