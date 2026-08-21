import { useCallback, useEffect, useState } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { BrowserRouter, NavLink, Navigate, Route, Routes } from "react-router-dom"
import { api, tokens, ApiError } from "./api/client"
import { Overview } from "./routes/Overview"
import { Verification } from "./routes/Verification"
import { TriageMonitor } from "./routes/TriageMonitor"
import { Login } from "./routes/Login"
import { Notice } from "./ui"

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 60_000 } },
})

const NAV = [
  { to: "/", label: "Overview", end: true },
  { to: "/verification", label: "Verification" },
  { to: "/triage", label: "Care Guide monitoring" },
] as const

type Session =
  | { state: "checking" }
  | { state: "anonymous" }
  | { state: "signed_in"; username: string }
  // A valid token belonging to somebody who is not a platform admin. Worth
  // distinguishing from "signed out": telling them to sign in again would
  // send them round a loop that cannot succeed.
  | { state: "forbidden" }

function Shell() {
  const [session, setSession] = useState<Session>({ state: "checking" })

  const load = useCallback(async () => {
    if (!tokens.access) {
      setSession({ state: "anonymous" })
      return
    }
    try {
      // There is no /platform/me. The overview IS the permission check: if it
      // returns, the caller is a superuser, which is the only fact this shell
      // needs. One endpoint fewer to keep in step with the permission class.
      await api.overview(1)
      setSession({ state: "signed_in", username: tokens.username })
    } catch (error) {
      if (error instanceof ApiError && error.status === 403) {
        setSession({ state: "forbidden" })
        return
      }
      tokens.clear()
      setSession({ state: "anonymous" })
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  if (session.state === "checking") {
    return <p className="p-6 text-small text-ink-muted">Loading...</p>
  }

  if (session.state === "anonymous") {
    return <Login onSignedIn={load} />
  }

  if (session.state === "forbidden") {
    return (
      <div className="mx-auto mt-24 max-w-md px-4">
        <h1 className="text-h2">Not a platform administrator</h1>
        <div className="mt-4">
          <Notice tone="info">
            This account signed in successfully but is not authorised for
            platform administration. Facility staff should use the reception
            app instead.
          </Notice>
        </div>
        <button
          className="ml-btn-secondary mt-4"
          onClick={() => {
            tokens.clear()
            setSession({ state: "anonymous" })
          }}
        >
          Sign in as somebody else
        </button>
      </div>
    )
  }

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[16rem_minmax(0,1fr)]">
      <aside className="border-b border-line bg-surface lg:sticky lg:top-0 lg:h-screen lg:border-b-0 lg:border-r">
        <div className="px-4 py-4">
          <p className="text-caption font-semibold uppercase tracking-widest text-primary">
            MediLink
          </p>
          <p className="mt-0.5 text-body font-semibold">Platform</p>
          {session.username && (
            <p className="text-small text-ink-muted">{session.username}</p>
          )}
        </div>

        <nav className="px-2 pb-3">
          <ul className="flex gap-1 overflow-x-auto lg:block lg:space-y-0.5 lg:overflow-visible">
            {NAV.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  end={"end" in item ? item.end : undefined}
                  className={({ isActive }) =>
                    "block whitespace-nowrap rounded-md px-3 py-2 text-body transition-colors " +
                    (isActive
                      ? "bg-primary-subtle font-medium text-primary"
                      : "text-ink-muted hover:bg-surface-sunken hover:text-ink")
                  }
                >
                  {item.label}
                </NavLink>
              </li>
            ))}
          </ul>

          <div className="mt-3 border-t border-line px-3 pt-3">
            {/* Django admin still owns CRUD. Linking to it rather than
                rebuilding forty change forms nobody asked for. */}
            <a
              className="block py-1 text-small text-ink-muted underline"
              href="/admin/"
            >
              Django admin
            </a>
            <button
              className="py-1 text-small text-ink-muted underline"
              onClick={() => {
                tokens.clear()
                queryClient.clear()
                setSession({ state: "anonymous" })
              }}
            >
              Sign out
            </button>
          </div>
        </nav>
      </aside>

      <main className="p-4">
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/verification" element={<Verification />} />
          <Route path="/triage" element={<TriageMonitor />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  )
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Shell />
      </BrowserRouter>
    </QueryClientProvider>
  )
}
