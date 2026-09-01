import { describe, expect, it } from "vitest"
import { screen } from "@testing-library/react"
import { WaitLine } from "./WaitLine"
import { renderWithI18n } from "../test/render"
import type { Wait } from "../api/types"

/**
 * Closes the Phase 0 checklist item "All four wait.status values render".
 *
 * WaitLine switches on a union type, so a missing branch returns undefined and
 * the component renders NOTHING - no error, no fallback, just a facility card
 * with a silently missing line. TypeScript catches an unhandled member of the
 * union only while the union is exact; these tests catch it either way.
 */

const AS_OF = new Date().toISOString()

const wait = (over: Partial<Wait>): Wait => ({
  status: "not_reported",
  minutes: null,
  people_waiting: null,
  as_of: AS_OF,
  ...over,
})

const ALL_STATUSES: Wait["status"][] = [
  "available",
  "not_reported",
  "insufficient_data",
  "closed",
]

describe("every status renders something", () => {
  it.each(ALL_STATUSES)("%s produces visible text", (status) => {
    const { container } = renderWithI18n(
      <WaitLine wait={wait({ status, minutes: status === "available" ? 43 : null })} />,
    )
    expect(container.textContent?.trim()).not.toBe("")
  })
})

describe("the honesty rule on screen", () => {
  it("shows a rounded estimate, never the raw number", () => {
    renderWithI18n(<WaitLine wait={wait({ status: "available", minutes: 43 })} />)
    // 43 rounds to 45. Printing "43" would claim a precision we do not have.
    expect(screen.getByText(/45/)).toBeInTheDocument()
    expect(screen.queryByText(/43/)).not.toBeInTheDocument()
  })

  it("never prints a number when the status is not available", () => {
    for (const status of ["not_reported", "insufficient_data", "closed"] as const) {
      const { container } = renderWithI18n(
        // minutes is deliberately populated: a status that is not `available`
        // must ignore it rather than leak it to the screen.
        <WaitLine wait={wait({ status, minutes: 90 })} />,
      )
      expect(container.textContent).not.toMatch(/\d+\s*min/i)
      expect(container.textContent).not.toMatch(/90/)
    }
  })

  it("says the wait is unavailable for both unknown-data statuses", () => {
    const { container: notReported } = renderWithI18n(
      <WaitLine wait={wait({ status: "not_reported" })} />,
    )
    const { container: insufficient } = renderWithI18n(
      <WaitLine wait={wait({ status: "insufficient_data" })} />,
    )
    // A patient cannot act on the difference between "nobody reports here" and
    // "not enough samples yet", so they must read identically.
    expect(notReported.textContent).toBe(insufficient.textContent)
  })

  it("renders unknown data more quietly than a real estimate", () => {
    const { container: unknown } = renderWithI18n(
      <WaitLine wait={wait({ status: "not_reported" })} />,
    )
    const { container: known } = renderWithI18n(
      <WaitLine wait={wait({ status: "available", minutes: 20 })} />,
    )
    // The visual hierarchy is load-bearing: a patient must be able to tell
    // known from unknown at a glance, without reading.
    expect(unknown.querySelector("p")?.className).toMatch(/text-neutral-500/)
    expect(known.querySelector("p")?.className).not.toMatch(/text-neutral-500/)
  })
})

describe("translation", () => {
  it.each(["rw", "en", "fr"])("renders in %s", (lang) => {
    const { container } = renderWithI18n(
      <WaitLine wait={wait({ status: "not_reported" })} />,
      { lang },
    )
    const text = container.textContent ?? ""
    expect(text.trim()).not.toBe("")
    // A missing key falls through to the key itself - that must never ship.
    expect(text).not.toContain("wait_unavailable")
  })
})
