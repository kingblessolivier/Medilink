import { act, renderHook, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { beforeEach, expect, it, vi } from "vitest"
import type { ReactNode } from "react"
import { AuthProvider, useAuth } from "./useAuth"
import { api, tokens } from "../api/client"
import type { Session } from "../api/types"

vi.mock("../api/client", () => ({
  api: { session: vi.fn(), me: vi.fn() },
  tokens: { access: "staff-token" as string | null, clear: vi.fn() },
}))

beforeEach(() => {
  vi.clearAllMocks()
  Object.defineProperty(tokens, "access", { value: "staff-token", writable: true, configurable: true })
})

function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}><AuthProvider>{children}</AuthProvider></QueryClientProvider>
  return { client, ...renderHook(useAuth, { wrapper }) }
}

it("clears account-scoped cache when signing out", async () => {
  vi.mocked(api.session).mockResolvedValue({ kind: "staff" } as Session)
  const { result, client } = setup()
  await waitFor(() => expect(result.current.session.state).toBe("signed_in"))
  client.setQueryData(["staff-me"], { privateName: "previous account" })
  client.setQueryData(["board"], { patients: ["private patient"] })
  act(() => result.current.signOut())
  expect(client.getQueryData(["staff-me"])).toBeUndefined()
  expect(client.getQueryData(["board"])).toBeUndefined()
  expect(result.current.session.state).toBe("anonymous")
})

it("does not restore a session that finishes after sign-out", async () => {
  let resolve!: (session: Session) => void
  vi.mocked(api.session).mockImplementation(() => new Promise(done => { resolve = done }))
  const { result } = setup()
  await waitFor(() => expect(api.session).toHaveBeenCalled())
  act(() => result.current.signOut())
  await act(async () => resolve({ kind: "staff" } as Session))
  expect(result.current.session.state).toBe("anonymous")
})
