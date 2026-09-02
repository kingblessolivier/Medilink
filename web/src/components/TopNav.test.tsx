import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { I18nProvider } from "../i18n"
import { TopNav } from "./TopNav"
import type { Session } from "../api/types"

/**
 * The bar is the only navigation on every patient route, so "which links show"
 * is a correctness question, not a styling one.
 *
 * The regression these guard: links were chosen by `session.kind` alone, and
 * staff/admin got none because their sections live in the DashboardShell
 * sidebar. That sidebar only exists on `/workspace` and `/platform` - so an
 * admin on the patient home had no sidebar AND no links, and no way out but
 * the wordmark.
 */

const session = (kind: Session["kind"]): Session =>
  ({ kind, username: "olivier" }) as Session

/**
 * The bar asks `/triage/status` whether the Care Guide may be offered, so it
 * needs a query client. The query is never resolved here, which is exactly
 * the state that matters: `useTriageStatus` defaults to unavailable, so these
 * assert the gate-shut navigation - the one that ships until a clinician
 * signs off.
 */
function renderNav(current: Session | null, path: string) {
  window.localStorage.setItem("medilink.language", "en")
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <I18nProvider>
        <MemoryRouter initialEntries={[path]}>
          <TopNav session={current} onSignOut={() => {}} />
        </MemoryRouter>
      </I18nProvider>
    </QueryClientProvider>,
  )
}

const PATIENT_LINKS = ["Home", "Facilities", "Doctors", "Insurance", "Visits"]

describe("patient routes always carry navigation", () => {
  it.each([
    ["signed out", null],
    ["a patient", session("patient")],
    ["a staff member", session("staff")],
    ["an admin", session("admin")],
  ])("shows the patient links to %s on the home route", (_who, current) => {
    renderNav(current as Session | null, "/")

    for (const label of PATIENT_LINKS) {
      expect(
        screen.getByRole("link", { name: new RegExp(`^${label}$`) }),
      ).toBeInTheDocument()
    }
  })

  it.each(["/search", "/doctors", "/insurance", "/visits", "/facility/x"])(
    "shows them to an admin on %s too",
    (path) => {
      renderNav(session("admin"), path)
      expect(screen.getByRole("link", { name: /^Doctors$/ })).toBeInTheDocument()
    },
  )
})

describe("dashboard surfaces defer to their own sidebar", () => {
  it.each(["/workspace", "/workspace/appointments", "/platform", "/platform/queue"])(
    "carries no top-bar links on %s",
    (path) => {
      renderNav(session("admin"), path)
      // Duplicating the sidebar here is what previously forced an empty
      // hamburger menu onto the dashboards.
      expect(screen.queryByRole("link", { name: /^Doctors$/ })).toBeNull()
    },
  )

  it("does not mistake a patient route that merely starts with the same letters", () => {
    // `/platform-guide` is not `/platform`. Prefix matching without the
    // boundary check would strip the nav from it.
    renderNav(session("admin"), "/platformx")
    expect(screen.getByRole("link", { name: /^Doctors$/ })).toBeInTheDocument()
  })
})

/**
 * The third link is the Care Guide when the clinician gate is open and the
 * doctor list when it is shut.
 *
 * Worth a test rather than a glance: the default is "shut", and a bug that
 * flipped it would put a symptom checker in front of patients that no
 * clinician has signed off - which is the exact outcome the gate exists to
 * prevent.
 */
describe("the Care Guide tab is gated on a clinician sign-off", () => {
  const renderWithGate = (available: boolean) => {
    window.localStorage.setItem("medilink.language", "en")
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })
    // Seed the cache directly rather than mocking fetch: it is the same key
    // `useTriageStatus` reads, and it keeps the test off the network.
    client.setQueryData(["triage", "status"], {
      available,
      protocol_version: "",
      approved_by: "",
      approved_on: "",
      reason: "",
    })
    return render(
      <QueryClientProvider client={client}>
        <I18nProvider>
          <MemoryRouter initialEntries={["/"]}>
            <TopNav session={null} onSignOut={() => {}} />
          </MemoryRouter>
        </I18nProvider>
      </QueryClientProvider>,
    )
  }

  it("shows Doctors while the gate is shut", () => {
    renderWithGate(false)

    expect(screen.getByRole("link", { name: /doctors/i })).toBeInTheDocument()
    expect(
      screen.queryByRole("link", { name: /care guide/i }),
    ).not.toBeInTheDocument()
  })

  it("shows the Care Guide once a clinician has signed off", () => {
    renderWithGate(true)

    expect(
      screen.getByRole("link", { name: /care guide/i }),
    ).toBeInTheDocument()
    // The tab is replaced, not added: five items is the maximum the bar holds.
    expect(
      screen.queryByRole("link", { name: /doctors/i }),
    ).not.toBeInTheDocument()
  })
})
