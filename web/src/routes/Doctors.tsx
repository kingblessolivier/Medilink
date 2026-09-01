import { useState } from "react"
import { useSearchParams } from "react-router-dom"
import { IconChevronRight, IconStethoscope } from "../ui/icons"
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
  const search = params.get("q") ?? undefined
  // Filters live in the URL so a result can be shared, which means this value
  // is whatever somebody typed or a stale link carries. The server takes four
  // languages and 400s on anything else, so an edited link would break the
  // whole page rather than drop one filter. Narrow it here instead.
  const language = asLanguage(params.get("language"))

  // Collapsed by default on a phone, always open from `sm` up. The count
  // goes in the button label so a collapsed panel never hides the fact that
  // the list is filtered.
  const [filtersOpen, setFiltersOpen] = useState(false)
  const activeFilters = [specialty, language].filter(Boolean).length

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
    <div className="ml-page py-6 pb-24 md:pb-10">
      <h1 className="text-h1">{t("doctors_title")}</h1>
      <p className="mt-1 max-w-prose text-body text-ink-muted">
        {t("doctors_body")}
      </p>

      {/* Search first and full width, filters under it.
          All three controls shared one three-column card, which gave the
          search field a third of the row - the same weight as "Language
          spoken", on the control people actually use. On a phone the two
          selects then stacked under it, so the list of doctors started below
          the fold. Search is now its own row; the selects sit under it on a
          wide screen and collapse behind a Filters button on a narrow one. */}
      <div className="mt-5 space-y-3">
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

        <div className="sm:hidden">
          <button
            type="button"
            onClick={() => setFiltersOpen((open) => !open)}
            aria-expanded={filtersOpen}
            aria-controls="doctor-filters"
            className="ml-btn-secondary w-full justify-between"
          >
            <span>
              {activeFilters > 0
                ? t("filters_active", { n: activeFilters })
                : t("filters")}
            </span>
            <IconChevronRight
              size={16}
              className={filtersOpen ? "rotate-90 transition-transform" : "transition-transform"}
            />
          </button>
        </div>

        <div
          id="doctor-filters"
          className={
            "gap-3 sm:grid sm:grid-cols-2 " + (filtersOpen ? "grid" : "hidden")
          }
        >
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
      </div>

      <div className="mb-3 mt-5 flex items-baseline justify-between">
        <h2 className="text-h3">
          {query.data ? t("n_results", { n: query.data.count }) : " "}
        </h2>
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
        <EmptyState icon={<IconStethoscope size={20} />}
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

const PROVIDER_LANGUAGES = ["rw", "en", "fr", "sw"] as const
type ProviderLanguage = (typeof PROVIDER_LANGUAGES)[number]

function asLanguage(value: string | null): ProviderLanguage | undefined {
  return PROVIDER_LANGUAGES.includes(value as ProviderLanguage)
    ? (value as ProviderLanguage)
    : undefined
}
