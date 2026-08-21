import { useCallback, useEffect, useState } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom"
import { api, tokens, type Me } from "./api/client"
import { useQueueActions } from "./hooks/useQueueActions"
import { Workspace } from "./components/Workspace"
import { Login } from "./routes/Login"
import { Reception } from "./routes/Reception"
import { Appointments } from "./routes/Appointments"
import { Doctors } from "./routes/Doctors"
import { Services } from "./routes/Services"
import { Reports } from "./routes/Reports"

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // A stale board is still useful at a reception desk; a blank one is not.
      gcTime: 60 * 60 * 1000,
      retry: 1,
    },
  },
})

type Session =
  | { state: "checking" }
  | { state: "anonymous" }
  | { state: "signed_in"; me: Me }

function Shell() {
  const [session, setSession] = useState<Session>({ state: "checking" })

  // Hoisted above the router: the offline queue and its pending count have to
  // survive navigation. A receptionist who checks somebody in, looks at the
  // appointment list and comes back must not find their pending actions gone.
  const actions = useQueueActions()

  const load = useCallback(async () => {
    if (!tokens.access) {
      setSession({ state: "anonymous" })
      return
    }
    try {
      setSession({ state: "signed_in", me: await api.me() })
    } catch {
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

  const me = session.me

  return (
    <Workspace
      me={me}
      online={actions.online}
      pendingCount={actions.pendingCount}
      syncing={actions.syncing}
      onSignOut={() => {
        tokens.clear()
        queryClient.clear()
        setSession({ state: "anonymous" })
      }}
    >
      <Routes>
        <Route path="/" element={<Reception me={me} actions={actions} />} />
        <Route
          path="/appointments"
          element={<Appointments canManage={me.can_manage_queue} />}
        />
        <Route path="/doctors" element={<Doctors me={me} />} />
        <Route path="/services" element={<Services me={me} />} />
        <Route path="/reports" element={<Reports />} />
        {/* A mistyped path lands at the desk, which is where the work is. */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Workspace>
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
