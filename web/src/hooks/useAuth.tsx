import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react"
import { useQueryClient } from "@tanstack/react-query"
import { api, tokens } from "../api/client"
import type { Patient, Session } from "../api/types"

/**
 * Who is signed in, across all three surfaces.
 *
 * One app now serves patients, facility staff and platform admins, so this
 * holds the `Session` the backend returns - its `kind` is what the router
 * uses to decide which surface a person gets.
 *
 * A patient additionally gets their full record, because the patient screens
 * need the insurer and home location that the lightweight session omits. That
 * is a second request, but only for patients: staff and admins never touch
 * `/me`, and loading a patient record for them would be both wasted and wrong.
 *
 * The authorisation itself is never decided here. This state picks which
 * screens to render; every endpoint re-checks on the server, because a client
 * that lies to itself is a UI bug and a client that is believed is a breach.
 */

type AuthState =
  | { state: "loading" }
  | { state: "anonymous" }
  | { state: "signed_in"; session: Session; patient: Patient | null }

type AuthValue = {
  session: AuthState
  reload: () => Promise<void>
  signOut: () => void
  setPatient: (patient: Patient) => void
}

const AuthContext = createContext<AuthValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const client = useQueryClient()
  const generation = useRef(0)
  const [session, setSession] = useState<AuthState>({ state: "loading" })

  const reload = useCallback(async () => {
    const attempt = ++generation.current
    setSession({ state: "loading" })
    // Cancel before clearing so an old request cannot refill another user's cache.
    await client.cancelQueries()
    client.clear()
    if (attempt !== generation.current) return
    if (!tokens.access) {
      setSession({ state: "anonymous" })
      return
    }
    try {
      const current = await api.session()
      const patient =
        current.kind === "patient" ? await api.me().catch(() => null) : null
      if (attempt !== generation.current) return
      setSession({ state: "signed_in", session: current, patient })
    } catch {
      if (attempt !== generation.current) return
      // An expired or malformed token. Clearing it stops an infinite retry
      // against a credential that will never work again.
      tokens.clear()
      setSession({ state: "anonymous" })
    }
  }, [client])

  useEffect(() => {
    void reload()
    const changed = (event: StorageEvent) => {
      if (event.key === "medilink.access" || event.key === null) void reload()
    }
    window.addEventListener("storage", changed)
    return () => window.removeEventListener("storage", changed)
  }, [reload])

  const signOut = useCallback(() => {
    ++generation.current
    void client.cancelQueries()
    client.clear()
    tokens.clear()
    setSession({ state: "anonymous" })
  }, [client])

  const setPatient = useCallback((patient: Patient) => {
    setSession((current) =>
      current.state === "signed_in"
        ? { ...current, patient }
        : current,
    )
  }, [])

  return (
    <AuthContext.Provider value={{ session, reload, signOut, setPatient }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthValue {
  const value = useContext(AuthContext)
  if (!value) throw new Error("useAuth must be used inside AuthProvider")
  return value
}

/**
 * The signed-in patient, or null.
 *
 * Null for staff and admins as well as for anonymous visitors - they are
 * signed in, but not as a patient, and a patient screen must not treat a
 * receptionist's session as if it were their own record.
 */
export function usePatient(): Patient | null {
  const { session } = useAuth()
  return session.state === "signed_in" ? session.patient : null
}

/** The raw session, for code that needs the kind rather than the record. */
export function useSession(): Session | null {
  const { session } = useAuth()
  return session.state === "signed_in" ? session.session : null
}
