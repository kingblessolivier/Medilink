import { useCallback, useEffect, useState } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { api, tokens, type Me } from "./api/client"
import { Login } from "./routes/Login"
import { Reception } from "./routes/Reception"

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
    return <p className="p-6 text-sm text-neutral-500">Loading...</p>
  }
  if (session.state === "anonymous") {
    return <Login onSignedIn={load} />
  }
  return (
    <Reception
      me={session.me}
      onSignOut={() => setSession({ state: "anonymous" })}
    />
  )
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Shell />
    </QueryClientProvider>
  )
}
