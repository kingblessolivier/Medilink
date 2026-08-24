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
 *
 * **Two steps, and the order matters.** Registration attaches credentials to
 * whatever patient record already holds the number, and every USSD, WhatsApp
 * and reception-desk patient has one with a blank password - so the number
 * has to be proved before anything is written. The code is asked for LAST,
 * once the rest of the form is valid, because it expires in five minutes and
 * sending it before somebody has chosen a username wastes most of that.
 */
export function Register() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const { reload } = useAuth()

  const [step, setStep] = useState<"details" | "code">("details")
  const [form, setForm] = useState({
    full_name: "",
    phone: "",
    username: "",
    password: "",
  })
  const [code, setCode] = useState("")
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

  function describe(err: unknown) {
    return err instanceof ApiRequestError
      ? // The server's own sentence is better than a generic one: "that
        // username is taken", "sign in instead", "that code is not correct".
        err.message
      : t("error_generic")
  }

  /** Step 1 -> send the code. Nothing is created yet.
   *  Also the resend handler, which has no event to cancel. */
  async function sendCode(event?: React.FormEvent) {
    event?.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await api.requestCode(form.phone.trim())
      setStep("code")
      setCode("")
    } catch (err) {
      setError(describe(err))
    } finally {
      setBusy(false)
    }
  }

  /** Step 2 -> prove the number, and only then create the account. */
  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const result = await api.register({
        username: form.username.trim(),
        password: form.password,
        phone: form.phone.trim(),
        code: code.trim(),
        full_name: form.full_name.trim() || undefined,
        consent,
      })
      tokens.save(result.access, result.refresh)
      await reload()
      navigate("/", { replace: true })
    } catch (err) {
      setError(describe(err))
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto w-full max-w-sm px-4 py-10">
      <h1 className="text-h1">{t("auth_create_account")}</h1>
      <p className="mt-1 text-small text-ink-muted">{t("auth_register_subtitle")}</p>

      <Card className="mt-6 p-4">
        {step === "details" ? (
        <form onSubmit={sendCode} className="space-y-3">
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
            {busy ? t("loading") : t("auth_send_code")}
          </button>
        </form>
        ) : (
        <form onSubmit={submit} className="space-y-3">
          {/* The number is repeated back, because a typo here is why the code
              never arrives - and the fix is to go back, not to wait. */}
          <p className="text-small text-ink-muted">
            {t("auth_code_sent_to")}{" "}
            <span className="font-medium text-ink">{form.phone.trim()}</span>
          </p>

          <Field label={t("auth_code")} hint={t("auth_code_hint")}>
            {(id, describedBy) => (
              <TextInput
                id={id}
                aria-describedby={describedBy}
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={6}
                placeholder="123456"
                value={code}
                onChange={(e) =>
                  setCode(e.target.value.replace(/\D/g, "").slice(0, 6))
                }
              />
            )}
          </Field>

          {error && (
            <p role="alert" className="text-small text-danger">
              {error}
            </p>
          )}

          <button
            className="ml-btn-primary w-full"
            disabled={busy || code.length < 6}
          >
            {busy ? t("loading") : t("auth_create_account")}
          </button>

          <div className="flex justify-between gap-3">
            <button
              type="button"
              className="text-small font-medium text-primary underline"
              onClick={() => {
                setStep("details")
                setError(null)
              }}
            >
              {t("auth_change_number")}
            </button>
            <button
              type="button"
              className="text-small font-medium text-primary underline disabled:opacity-50"
              disabled={busy}
              onClick={() => sendCode()}
            >
              {t("auth_resend_code")}
            </button>
          </div>
        </form>
        )}
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
