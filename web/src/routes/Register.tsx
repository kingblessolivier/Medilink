import { useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { api, ApiRequestError, tokens } from "../api/client"
import { useI18n } from "../i18n"
import { useAuth } from "../hooks/useAuth"
import { Card, Field, Notice, TextInput } from "../ui"

/**
 * Patient registration.
 *
 * Staff and admin accounts are not self-served - MediLink issues them - so
 * this form only ever creates a patient.
 *
 * The phone number is still required even though sign-in no longer uses a
 * code: it is how the queue reaches somebody when they are called, how USSD
 * recognises them if they ever ring in, and how they get back in if they
 * forget the password. An account with no phone would be an account MediLink
 * cannot contact, which for a health service is not an account at all.
 */
export function Register() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const { reload } = useAuth()

  const [form, setForm] = useState({
    full_name: "",
    phone: "",
    username: "",
    password: "",
  })
  // Unticked by default and required by the server. A pre-ticked box is not
  // consent - Rwanda Law 058/2021, docs/08 section 6.
  const [consent, setConsent] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const set = (key: keyof typeof form) => (value: string) =>
    setForm((f) => ({ ...f, [key]: value }))

  const ready =
    form.phone.trim() &&
    form.username.trim().length >= 3 &&
    form.password.length >= 8 &&
    consent

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const result = await api.register({
        username: form.username.trim(),
        password: form.password,
        phone: form.phone.trim(),
        full_name: form.full_name.trim() || undefined,
        consent,
      })
      tokens.save(result.access, result.refresh)
      await reload()
      navigate("/", { replace: true })
    } catch (err) {
      setError(
        err instanceof ApiRequestError
          ? // 409 already carries a usable sentence from the server - "that
            // username is taken", or "sign in instead" - so it is shown as
            // written rather than flattened into a generic failure.
            err.message
          : t("error_generic"),
      )
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto w-full max-w-sm px-4 py-10">
      <h1 className="text-h1">{t("auth_create_account")}</h1>
      <p className="mt-1 text-small text-ink-muted">{t("auth_register_subtitle")}</p>

      <Card className="mt-6 p-4">
        <form onSubmit={submit} className="space-y-3">
          <Field label={t("auth_full_name")} hint={t("auth_full_name_hint")}>
            {(id, describedBy) => (
              <TextInput
                id={id}
                aria-describedby={describedBy}
                value={form.full_name}
                onChange={(e) => set("full_name")(e.target.value)}
                autoComplete="name"
              />
            )}
          </Field>

          <Field label={t("auth_phone")} hint={t("auth_phone_hint")}>
            {(id, describedBy) => (
              <TextInput
                id={id}
                aria-describedby={describedBy}
                inputMode="tel"
                placeholder="078..."
                value={form.phone}
                onChange={(e) => set("phone")(e.target.value)}
                autoComplete="tel"
              />
            )}
          </Field>

          <Field label={t("auth_username")} hint={t("auth_username_rules")}>
            {(id, describedBy) => (
              <TextInput
                id={id}
                aria-describedby={describedBy}
                value={form.username}
                onChange={(e) => set("username")(e.target.value)}
                autoComplete="username"
                autoCapitalize="none"
                spellCheck={false}
              />
            )}
          </Field>

          <Field label={t("auth_password")} hint={t("auth_password_rules")}>
            {(id, describedBy) => (
              <TextInput
                id={id}
                aria-describedby={describedBy}
                type="password"
                value={form.password}
                onChange={(e) => set("password")(e.target.value)}
                autoComplete="new-password"
              />
            )}
          </Field>

          <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-line bg-surface-sunken/50 p-3">
            <input
              type="checkbox"
              className="ml-checkbox mt-0.5"
              checked={consent}
              onChange={(e) => setConsent(e.target.checked)}
            />
            <span className="text-small text-ink">
              {t("auth_consent")}{" "}
              <Link to="/privacy" className="font-medium text-primary underline">
                {t("auth_privacy_notice")}
              </Link>
            </span>
          </label>

          {error && (
            <p role="alert" className="text-small text-danger">
              {error}
            </p>
          )}

          <button className="ml-btn-primary w-full" disabled={busy || !ready}>
            {busy ? t("loading") : t("auth_create_account")}
          </button>
        </form>
      </Card>

      <p className="mt-4 text-center text-body">
        {t("auth_have_account")}{" "}
        <Link to="/sign-in" className="font-medium text-primary underline">
          {t("auth_sign_in")}
        </Link>
      </p>

      <div className="mt-6">
        <Notice tone="info">{t("auth_privacy_note")}</Notice>
      </div>
    </div>
  )
}
