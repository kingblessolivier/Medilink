import { useState } from "react"
import { api } from "../api/client"

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
    } catch {
      setError("Wrong username or password.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto mt-24 max-w-sm px-4">
      <h1 className="mb-1 text-h2">MediLink Reception</h1>
      <p className="mb-6 text-small text-ink-muted">
        Sign in with the account your facility administrator created.
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
          Sign in
        </button>
      </form>
    </div>
  )
}
