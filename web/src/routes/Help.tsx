import { Link } from "react-router-dom"
import { useI18n } from "../i18n"
import { Notice } from "../ui"

/**
 * How to do the things MediLink asks people to do.
 *
 * Ordered by what actually goes wrong, not by feature. The emergency notice
 * is first and is not a section among sections: somebody who needs it is not
 * reading a help page in order.
 *
 * "If a facility turns you away" earns its place because it is the failure
 * this product can genuinely cause. Insurance data comes from the facility
 * and can be out of date, so a patient can travel on the strength of
 * something we showed them and be refused at the counter. Saying so, and
 * saying what to do about it, is more use than pretending it cannot happen.
 */
export function Help() {
  const { t } = useI18n()
  const emergency = t("emergency_number")

  return (
    <div className="ml-page py-8 pb-24 md:pb-10">
      <header className="max-w-prose">
        <h1 className="text-h1">{t("help_title")}</h1>
      </header>

      {/* Not a section among sections. Somebody who needs this is not
          reading in order. */}
      <div className="mt-5 max-w-prose">
        <Notice tone="warning">
          <strong className="block">{t("help_emergency_title")}</strong>
          <span className="mt-0.5 block">
            {t("help_emergency_body", { number: emergency })}
          </span>
          <a
            href={`tel:${emergency}`}
            className="ml-btn-primary ml-btn-sm mt-3 inline-flex"
          >
            {t("footer_emergency_action", { number: emergency })}
          </a>
        </Notice>
      </div>

      <div className="mt-8 max-w-prose space-y-7">
        <Section title={t("help_book_title")} body={t("help_book_body")} />
        <Section title={t("help_queue_title")} body={t("help_queue_body")} />
        <Section
          title={t("help_turned_away_title")}
          body={t("help_turned_away_body")}
        />
        <Section title={t("help_data_title")} body={t("help_data_body")}>
          <Link
            to="/profile"
            className="mt-2 inline-flex text-body-lg font-medium text-primary underline"
          >
            {t("nav_profile")}
          </Link>
        </Section>
        <Section
          title={t("help_contact_title")}
          body={t("help_contact_body")}
        />
      </div>

      <nav className="mt-10 flex flex-wrap gap-3 border-t border-n200 pt-6">
        <Link to="/about" className="ml-btn-secondary ml-btn-sm">
          {t("about_title")}
        </Link>
        <Link to="/privacy" className="ml-btn-ghost ml-btn-sm">
          {t("footer_privacy_link")}
        </Link>
      </nav>
    </div>
  )
}

function Section({
  title,
  body,
  children,
}: {
  title: string
  body: string
  children?: React.ReactNode
}) {
  return (
    <section>
      <h2 className="text-h3">{title}</h2>
      <p className="mt-1.5 text-body-lg text-n700">{body}</p>
      {children}
    </section>
  )
}
