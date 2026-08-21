import { useState } from "react"
import { Link, useNavigate, useSearchParams } from "react-router-dom"
import { api, ApiRequestError, tokens } from "../api/client"
import { useI18n } from "../i18n"
import { useAuth } from "../hooks/useAuth"
import { homeFor } from "../components/TopNav"
import { Card, Field, Notice, TextInput } from "../ui"

/**
 * One sign-in, three kinds of user.
 *
 * The form does not ask which you are, and it must not: a receptionist is not
 * going to pick "I am staff" from a dropdown every morning, and asking would
 * also tell an attacker which usernames are which. The server decides, and the
 * client routes on the `kind` that comes back.
 *
 * A patient may type either their username or their phone number, because the
 * phone is the one credential every patient already knows they have - it is
 * what USSD, WhatsApp and every SMS we send uses.
 */
export function SignIn() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const { reload } = useAuth()
  const [params] = useSearchParams()

  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const result = await api.signIn(username.trim(), password)
      tokens.save(result.access, result.refresh)
      await reload()

      if (result.session.kind === null) {
        // Authenticated, but there is no surface for them. Saying so beats
        // dropping them on a patient home page that will not work.
        setError(t("auth_no_surface"))
        tokens.clear()
        setBusy(false)
        return
      }

      // `next` only ever comes from our own guards, and is compared against a
      // leading slash so it cannot be turned into an off-site redirect.
      const next = params.get("next")
      const target =
        next && next.startsWith("/") && !next.startsWith("//")
          ? next
          : homeFor(result.session)
      navigate(target, { replace: true })
    } catch (err) {
      setError(
        err instanceof ApiRequestError && err.status === 401
          ? t("auth_bad_credentials")
          : err instanceof ApiRequestError && err.status === 429
            ? t("auth_too_many")
            : t("error_generic"),
      )
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto w-full max-w-sm px-4 py-10">
      <h1 className="text-h1">{t("auth_sign_in")}</h1>
      <p className="mt-1 text-small text-ink-muted">{t("auth_subtitle")}</p>

      <Card className="mt-6 space-y-3 p-4">
        <form onSubmit={submit} className="space-y-3">
          <Field label={t("auth_username")} hint={t("auth_username_hint")}>
            {(id, describedBy) => (
              <TextInput
                id={id}
                aria-describedby={describedBy}
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoFocus
                autoComplete="username"
                autoCapitalize="none"
                spellCheck={false}
              />
            )}
          </Field>

          <Field label={t("auth_password")}>
            {(id, describedBy) => (
              <TextInput
                id={id}
                aria-describedby={describedBy}
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
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
            disabled={busy || !username.trim() || !password}
          >
            {busy ? t("loading") : t("auth_sign_in")}
          </button>
        </form>
      </Card>

      <p className="mt-4 text-center text-body">
        {t("auth_no_account")}{" "}
        <Link to="/register" className="font-medium text-primary underline">
          {t("auth_create_account")}
        </Link>
      </p>

      <div className="mt-6">
        {/* Staff and admin accounts are issued, never self-served. Saying so
            stops a receptionist trying to register and ending up with a
            patient account they cannot run a desk from. */}
        <Notice tone="info">{t("auth_staff_note")}</Notice>
      </div>
    </div>
  )
}
