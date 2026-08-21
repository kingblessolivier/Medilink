import { Link } from "react-router-dom"
import { useI18n } from "../i18n"
import { Notice } from "../ui"

/**
 * The privacy notice.
 *
 * Every statement here describes behaviour that exists in the code, and was
 * written by reading it rather than from a template:
 *
 *   what is stored      apps/patients/models.py
 *   who can see it      apps/staff/permissions.py, apps/platform_admin
 *   the audit trail     apps/patients/models.PatientAccessLog
 *   export and erasure  apps/patients/privacy.py
 *   triage answers      apps/triage/models.TriageOutcome
 *
 * The banner at the top is not boilerplate. A privacy notice is a legal
 * document under Rwanda Law 058/2021, and this one has not been through a
 * lawyer. Saying so is more honest than implying a review that has not
 * happened - and it is a launch blocker, tracked in docs/08 section 9.
 */
export function Privacy() {
  const { t } = useI18n()

  return (
    <div className="ml-shell py-10">
      <div className="max-w-prose">
        <h1 className="text-h1">{t("privacy_title")}</h1>
        <p className="mt-2 text-body text-ink-muted">{t("privacy_version")}</p>

        <div className="mt-6">
          <Notice tone="warning">{t("privacy_draft_warning")}</Notice>
        </div>

        <Section title={t("privacy_what_title")}>
          <ul className="ml-4 list-disc space-y-1.5">
            <li>{t("privacy_what_phone")}</li>
            <li>{t("privacy_what_name")}</li>
            <li>{t("privacy_what_insurer")}</li>
            <li>{t("privacy_what_location")}</li>
            <li>{t("privacy_what_visits")}</li>
          </ul>
          <p className="mt-3">{t("privacy_what_not")}</p>
        </Section>

        <Section title={t("privacy_who_title")}>
          <p>{t("privacy_who_body")}</p>
          <p className="mt-3">{t("privacy_who_audit")}</p>
        </Section>

        <Section title={t("privacy_triage_title")}>
          <p>{t("privacy_triage_body")}</p>
        </Section>

        <Section title={t("privacy_rights_title")}>
          <p>{t("privacy_rights_body")}</p>
          <div className="mt-4 flex flex-wrap gap-2">
            <Link to="/profile" className="ml-btn-secondary ml-btn-sm">
              {t("privacy_rights_action")}
            </Link>
          </div>
        </Section>

        <Section title={t("privacy_contact_title")}>
          <p>{t("privacy_contact_body")}</p>
        </Section>
      </div>
    </div>
  )
}

function Section({
  title,
  children,
}: {
  title: string
  children: React.ReactNode
}) {
  return (
    <section className="ml-section">
      <h2 className="text-h2">{title}</h2>
      <div className="mt-3 space-y-2 text-body text-ink-muted">{children}</div>
    </section>
  )
}
