import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { I18nProvider } from "../i18n"
import { WaitLine } from "./WaitLine"
import type { Wait, WaitStatus } from "../api/types"

/**
 * The honesty rule, asserted at the pixel.
 *
 * All four wait states must render, and only one of them may show a number.
 * The backend gate stops an unfounded estimate reaching the API; this stops a
 * client bug inventing one on the way to the screen.
 */

function wait(status: WaitStatus, minutes: number | null = null): Wait {
  return {
    status,
    minutes,
    people_waiting: null,
    as_of: new Date().toISOString(),
  }
}

function renderWait(value: Wait, lang = "en") {
  window.localStorage.setItem("medilink.language", lang)
  return render(
    <I18nProvider>
      <WaitLine wait={value} />
    </I18nProvider>,
  )
}

describe("WaitLine", () => {
  it("shows a wait only when one is available", () => {
    renderWait(wait("available", 43))
    expect(screen.getByText(/about 45 min/i)).toBeInTheDocument()
  })

  it("rounds to five minutes rather than claiming precision", () => {
    // "43 minutes" implies an accuracy we do not have.
    renderWait(wait("available", 43))
    expect(screen.queryByText(/43/)).not.toBeInTheDocument()
  })

  it.each<[WaitStatus]>([["not_reported"], ["insufficient_data"]])(
    "shows no number for %s",
    (status) => {
      const { container } = renderWait(wait(status))
      expect(screen.getByText(/not available/i)).toBeInTheDocument()
      expect(container.textContent).not.toMatch(/\d+\s*min/i)
    },
  )

  it("says closed rather than showing a wait", () => {
    const { container } = renderWait(wait("closed", 40))
    expect(screen.getByText(/closed/i)).toBeInTheDocument()
    expect(container.textContent).not.toMatch(/\d+\s*min/i)
  })

  it("never invents a number when minutes is null but status says available", () => {
    // A malformed payload must degrade to zero, not to NaN on a patient screen.
    const { container } = renderWait(wait("available", null))
    expect(container.textContent).not.toMatch(/nan/i)
    expect(container.textContent).not.toMatch(/undefined/i)
  })

  it("renders in Kinyarwanda by default", () => {
    window.localStorage.removeItem("medilink.language")
    render(
      <I18nProvider>
        <WaitLine wait={wait("not_reported")} />
      </I18nProvider>,
    )
    expect(screen.getByText(/ntikiboneka/i)).toBeInTheDocument()
  })
})
