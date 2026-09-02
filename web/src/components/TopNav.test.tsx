import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
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

function renderNav(current: Session | null, path: string) {
  window.localStorage.setItem("medilink.language", "en")
  return render(
    <I18nProvider>
      <MemoryRouter initialEntries={[path]}>
        <TopNav session={current} onSignOut={() => {}} />
      </MemoryRouter>
    </I18nProvider>,
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
