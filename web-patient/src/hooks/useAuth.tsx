import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react"
import { api, tokens } from "../api/client"
import type { Patient } from "../api/types"

type Session =
  | { state: "loading" }
  | { state: "anonymous" }
  | { state: "signed_in"; patient: Patient }

type AuthValue = {
  session: Session
  reload: () => Promise<void>
  signOut: () => void
  setPatient: (patient: Patient) => void
}

const AuthContext = createContext<AuthValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session>({ state: "loading" })

  const reload = useCallback(async () => {
    if (!tokens.access) {
      setSession({ state: "anonymous" })
      return
    }
    try {
      setSession({ state: "signed_in", patient: await api.me() })
    } catch {
      tokens.clear()
      setSession({ state: "anonymous" })
    }
  }, [])

  useEffect(() => {
    void reload()
  }, [reload])

  const signOut = useCallback(() => {
    tokens.clear()
    setSession({ state: "anonymous" })
  }, [])

  const setPatient = useCallback((patient: Patient) => {
    setSession({ state: "signed_in", patient })
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

/** Convenience: the signed-in patient, or null. */
export function usePatient(): Patient | null {
  const { session } = useAuth()
  return session.state === "signed_in" ? session.patient : null
}
