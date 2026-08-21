import { useState } from "react"
import { api, ApiError } from "../api/client"

/**
 * Platform admin sign-in.
 *
 * The same token endpoint the reception app uses - the difference is what the
 * account is, not how it authenticates. A non-superuser can obtain a token
 * here and will then be refused by every endpoint, which is the correct
 * behaviour: the permission check belongs on the resource, not the login form.
 */
export function Login({ onSignedIn }: { onSignedIn: () => void }) {
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await api.login(username, password)
      onSignedIn()
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 401
          ? "That username and password did not match."
          : "Could not sign in. Check your connection and try again.",
      )
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto mt-24 max-w-sm px-4">
      <p className="text-caption font-semibold uppercase tracking-widest text-primary">
        MediLink
      </p>
      <h1 className="mb-1 text-h2">Platform administration</h1>
      <p className="mb-6 text-small text-ink-muted">
        Restricted to MediLink platform administrators.
      </p>

      <form onSubmit={submit} className="ml-card space-y-3 p-4">
        <label className="block">
          <span className="mb-1 block text-small text-ink-muted">Username</span>
          <input
            className="ml-field"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoFocus
            autoComplete="username"
          />
        </label>

        <label className="block">
          <span className="mb-1 block text-small text-ink-muted">Password</span>
          <input
            className="ml-field"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
          />
        </label>

        {error && <p className="text-small text-danger">{error}</p>}

        <button className="ml-btn-primary w-full" disabled={busy}>
          {busy ? "Signing in..." : "Sign in"}
        </button>
      </form>
    </div>
  )
}
