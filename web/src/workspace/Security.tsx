import { useState, type FormEvent } from "react"
import { api, tokens } from "../api/client"
import { useAuth } from "../hooks/useAuth"
import { useI18n } from "../i18n"
import { Button } from "../ui"

export function Security() {
  const { t } = useI18n()
  const { reload } = useAuth()
  const [current, setCurrent] = useState("")
  const [password, setPassword] = useState("")
  const [confirmation, setConfirmation] = useState("")
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState("")
  async function submit(event: FormEvent) {
    event.preventDefault()
    if (busy) return
    if (password !== confirmation) { setMessage(t("security_mismatch")); return }
    setBusy(true)
    setMessage("")
    try {
      const result = await api.changePassword({ current_password: current, new_password: password })
      tokens.save(result.access, result.refresh)
      setCurrent(""); setPassword(""); setConfirmation("")
      await reload()
      setMessage(t("security_saved"))
    } catch {
      setMessage(t("security_failed"))
    } finally { setBusy(false) }
  }
  return <section className="max-w-lg space-y-6">
    <h1 className="text-2xl font-extrabold text-n900">{t("security_title")}</h1>
    <form onSubmit={submit} className="space-y-6">
      {([
        ["current", current, setCurrent, "current-password", "security_current"],
        ["new", password, setPassword, "new-password", "security_new"],
        ["confirm", confirmation, setConfirmation, "new-password", "security_confirm"],
      ] as const).map(([id, value, update, autocomplete, label]) => <label key={id} className="block space-y-2" htmlFor={`password-${id}`}>
        <span className="text-sm font-medium text-n700">{t(label)}</span>
        <input id={`password-${id}`} type="password" autoComplete={autocomplete} required minLength={id === "current" ? 1 : 8} maxLength={128} value={value} onChange={event => update(event.target.value)} disabled={busy} className="min-h-11 w-full rounded-input border border-n300 bg-white px-4 text-n900 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20" />
      </label>)}
      {message && <p role="status" className="text-sm text-n700">{message}</p>}
      <Button type="submit" loading={busy}>{t("security_submit")}</Button>
    </form>
  </section>
}
