import { Link } from "react-router-dom"
import { useI18n } from "../i18n"
import { useServiceTypes } from "../hooks/useNearbyFacilities"
import { useSpecialties } from "../hooks/useSpecialties"
import { ErrorState, ListSkeleton } from "../ui"
import { IconChevronRight, IconHospital, IconStethoscope } from "../ui/icons"

/**
 * The services directory.
 *
 * `/service/:code` already existed with no index above it, so the only way to
 * reach a service was to already know its name. This is the index.
 *
 * A list, not a grid of cards. Fifteen services with a name each is exactly
 * the content a list is for, and turning each into a tile would make it
 * harder to scan, not easier - see the rule about not making everything a
 * card.
 *
 * Specialties sit alongside services because a patient does not know which
 * of the two they are looking for, and the distinction is ours rather than
 * theirs. A specialty routes into the facility search; a service routes to
 * its own page.
 */
export function Services() {
  const { t, lang } = useI18n()
  const services = useServiceTypes()
  const specialties = useSpecialties()

  const label = (s: { name_rw: string; name_en: string; name_fr: string }) =>
    lang === "rw" ? s.name_rw : lang === "fr" ? s.name_fr : s.name_en

  return (
    <div className="ml-shell py-6 pb-24 md:pb-10">
      <header className="max-w-prose">
        <h1 className="text-h1">{t("services_title")}</h1>
        <p className="mt-2 text-body-lg text-n700">{t("services_intro")}</p>
      </header>

      <section className="mt-8">
        <h2 className="text-h2 mb-3">{t("services_all")}</h2>

        {services.isLoading && <ListSkeleton rows={5} />}
        {services.isError && <ErrorState title={t("error_generic")} />}

        {services.data && (
          <ul className="divide-y divide-n200 rounded-lg border border-n200 bg-white">
            {services.data.results.map((service) => (
              <li key={service.code}>
                <Link
                  to={`/service/${service.code}`}
                  className="flex min-h-touch items-center gap-3 px-4 py-3 hover:bg-n100"
                >
                  <span className="ml-icon-plate bg-primary-light text-primary">
                    <IconHospital size={17} />
                  </span>
                  <span className="min-w-0 flex-1 text-body-lg text-n900">
                    {label(service)}
                  </span>
                  <IconChevronRight size={16} className="text-n600" />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* A patient does not know whether they want a service or a specialty,
          and the distinction is ours rather than theirs. */}
      {specialties.data && specialties.data.results.length > 0 && (
        <section className="mt-8">
          <h2 className="text-h2 mb-3">{t("services_specialties")}</h2>
          <ul className="divide-y divide-n200 rounded-lg border border-n200 bg-white">
            {specialties.data.results.map((specialty) => (
              <li key={specialty.code}>
                <Link
                  to={`/search?specialty=${specialty.code}`}
                  className="flex min-h-touch items-center gap-3 px-4 py-3 hover:bg-n100"
                >
                  <span className="ml-icon-plate bg-primary-light text-primary">
                    <IconStethoscope size={17} />
                  </span>
                  <span className="min-w-0 flex-1 text-body-lg text-n900">
                    {label(specialty)}
                  </span>
                  <IconChevronRight size={16} className="text-n600" />
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
