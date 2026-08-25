import { Link } from "react-router-dom"
import { useI18n } from "../i18n"

/**
 * Who runs this, and what its words mean.
 *
 * The brief lists About as secondary navigation and it had no destination.
 * For a health service asking somebody for a phone number and a consent tick,
 * "who is behind this" is not decoration.
 *
 * Most of the page exists to define three words the product uses constantly
 * and which a patient would otherwise have to guess at: **verified**, the
 * **wait time**, and what MediLink can say about **insurance**. Each
 * definition is narrower than a reader might assume, which is the point of
 * writing it down.
 *
 * No figures. There are no honest adoption numbers to quote yet, and the rule
 * against inventing them applies here more than anywhere - this is the page
 * somebody reads when deciding whether to trust the rest.
 */
export function About() {
  const { t } = useI18n()

  return (
    <div className="ml-page py-8 pb-24 md:pb-10">
      <header className="max-w-prose">
        <h1 className="text-h1">{t("about_title")}</h1>
        <p className="mt-3 text-body-lg text-ink-muted">{t("about_lede")}</p>
      </header>

      <div className="mt-8 max-w-prose space-y-7">
        <Section title={t("about_what_title")} body={t("about_what_body")} />
        <Section
          title={t("about_verified_title")}
          body={t("about_verified_body")}
        />
        <Section title={t("about_wait_title")} body={t("about_wait_body")} />
        <Section
          title={t("about_insurance_title")}
          body={t("about_insurance_body")}
        />
        <Section
          title={t("about_privacy_title")}
          body={t("about_privacy_body")}
        />
      </div>

      <nav className="mt-10 flex flex-wrap gap-3 border-t border-line pt-6">
        <Link to="/help" className="ml-btn-secondary ml-btn-sm">
          {t("help_title")}
        </Link>
        <Link to="/privacy" className="ml-btn-tertiary ml-btn-sm">
          {t("footer_privacy_link")}
        </Link>
      </nav>
    </div>
  )
}

function Section({ title, body }: { title: string; body: string }) {
  return (
    <section>
      <h2 className="text-h3">{title}</h2>
      <p className="mt-1.5 text-body text-ink-muted">{body}</p>
    </section>
  )
}
