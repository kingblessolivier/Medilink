import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { api, ApiRequestError } from "../api/client"
import { useI18n } from "../i18n"
import { useAuth } from "../hooks/useAuth"

/**
 * Phone plus a six-digit code. No passwords: patients will not manage them,
 * and reuse across a health service would be worse than an OTP.
 */
export function SignIn() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const { setPatient } = useAuth()

  const [step, setStep] = useState<"phone" | "code">("phone")
  const [phone, setPhone] = useState("")
  const [code, setCode] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function sendCode(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await api.requestCode(phone.trim())
      setStep("code")
    } catch (err) {
      setError(
        err instanceof ApiRequestError && err.status === 429
          ? t("auth_too_many")
          : t("error_generic"),
      )
    } finally {
      setBusy(false)
    }
  }

  async function verify(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      setPatient(await api.verifyCode(phone.trim(), code.trim()))
      navigate("/")
    } catch (err) {
      setError(
        err instanceof ApiRequestError ? err.message : t("error_generic"),
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto mt-16 max-w-sm px-4">
      <h1 className="mb-1 text-h1">{t("auth_title")}</h1>
      <p className="mb-6 text-small text-ink-muted">{t("auth_subtitle")}</p>

      {step === "phone" ? (
        <form onSubmit={sendCode} className="ml-card space-y-3 p-4">
          <label className="block">
            <span className="mb-1 block text-small text-ink-muted">
              {t("auth_phone")}
            </span>
            <input
              className="ml-field"
              inputMode="tel"
              autoComplete="tel"
              placeholder="078..."
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              autoFocus
            />
          </label>
          {error && <p className="text-small text-danger">{error}</p>}
          <button className="ml-btn-primary w-full" disabled={busy || !phone.trim()}>
            {t("auth_send_code")}
          </button>
        </form>
      ) : (
        <form onSubmit={verify} className="ml-card space-y-3 p-4">
          <p className="text-small text-ink-muted">
            {t("auth_code_sent", { phone })}
          </p>
          <label className="block">
            <span className="mb-1 block text-small text-ink-muted">
              {t("auth_code")}
            </span>
            <input
              className="ml-field text-center text-2xl tracking-[0.4em]"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
              autoFocus
            />
          </label>
          {error && <p className="text-small text-danger">{error}</p>}
          <button
            className="ml-btn-primary w-full"
            disabled={busy || code.length !== 6}
          >
            {t("auth_verify")}
          </button>
          <button
            type="button"
            className="w-full py-2 text-small text-primary"
            onClick={() => {
              setStep("phone")
              setCode("")
              setError(null)
            }}
          >
            {t("auth_change_number")}
          </button>
        </form>
      )}
    </div>
  )
}
