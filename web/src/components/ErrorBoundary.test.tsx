import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { I18nProvider } from "../i18n"
import { ErrorBoundary } from "./ErrorBoundary"

/**
 * There were no error boundaries anywhere in this app.
 *
 * One unguarded array read in a card component took out the header, the
 * bottom nav and every route with it, leaving a white page and no way back
 * except knowing to reload. These tests exist so that cannot return quietly.
 */

function Boom(): JSX.Element {
  throw new Error("component exploded")
}

function renderWithin(ui: React.ReactNode, lang = "en") {
  window.localStorage.setItem("medilink.language", lang)
  return render(
    <I18nProvider>
      <MemoryRouter>{ui}</MemoryRouter>
    </I18nProvider>,
  )
}

describe("ErrorBoundary", () => {
  beforeEach(() => {
    // React logs the caught error itself; the boundary logs it again on
    // purpose. Neither is a test failure, and both make the output unreadable.
    vi.spyOn(console, "error").mockImplementation(() => {})
  })

  afterEach(() => {
    vi.restoreAllMocks()
    window.localStorage.clear()
  })

  it("shows a recovery screen instead of a blank page", () => {
    renderWithin(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    )

    expect(screen.getByRole("alert")).toBeInTheDocument()
    expect(
      screen.getByText(/something went wrong on this screen/i),
    ).toBeInTheDocument()
  })

  it("offers both a retry and a way back to the start", () => {
    renderWithin(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    )

    expect(
      screen.getByRole("button", { name: /try this screen again/i }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole("link", { name: /back to the start/i }),
    ).toHaveAttribute("href", "/")
  })

  it("renders the recovery screen in the patient's language", () => {
    renderWithin(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
      "rw",
    )

    // An error page in the wrong language is barely better than a blank one,
    // which is why the screen is a function component and not the class.
    expect(
      screen.getByText(/hari ikitagenze neza kuri iyi paji/i),
    ).toBeInTheDocument()
  })

  it("lets the user retry back into a working screen", async () => {
    const user = userEvent.setup()

    // The shape of a transient data problem: the screen fails, whatever
    // caused it resolves, and the person tries again.
    let broken = true
    function Flaky() {
      if (broken) throw new Error("bad data")
      return <p>recovered</p>
    }

    renderWithin(
      <ErrorBoundary>
        <Flaky />
      </ErrorBoundary>,
    )
    expect(screen.getByRole("alert")).toBeInTheDocument()

    broken = false
    await user.click(screen.getByRole("button", { name: /try this screen/i }))

    expect(await screen.findByText("recovered")).toBeInTheDocument()
    expect(screen.queryByRole("alert")).not.toBeInTheDocument()
  })

  it("recovers when the route changes, without a reload", () => {
    const { rerender } = renderWithin(
      <ErrorBoundary resetKey="/doctors">
        <Boom />
      </ErrorBoundary>,
    )
    expect(screen.getByRole("alert")).toBeInTheDocument()

    // Navigating away from a broken screen must not stay broken.
    rerender(
      <I18nProvider>
        <MemoryRouter>
          <ErrorBoundary resetKey="/visits">
            <p>a different screen</p>
          </ErrorBoundary>
        </MemoryRouter>
      </I18nProvider>,
    )

    expect(screen.getByText("a different screen")).toBeInTheDocument()
    expect(screen.queryByRole("alert")).not.toBeInTheDocument()
  })

  it("passes children through untouched when nothing throws", () => {
    renderWithin(
      <ErrorBoundary>
        <p>the actual screen</p>
      </ErrorBoundary>,
    )

    expect(screen.getByText("the actual screen")).toBeInTheDocument()
    expect(screen.queryByRole("alert")).not.toBeInTheDocument()
  })
})
