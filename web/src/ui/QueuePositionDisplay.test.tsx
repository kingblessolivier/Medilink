import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import rw from "../i18n/rw.json"
import { I18nProvider } from "../i18n"
import {
  QueuePositionDisplay,
  type QueuePositionDisplayProps,
} from "./QueuePositionDisplay"

/**
 * These are the product's honesty rules, not styling assertions. If one fails,
 * what a patient sees is a fabricated wait time or a departure time built out
 * of nothing - the one thing this product cannot recover from.
 *
 * Assertions run against the Kinyarwanda bundle because that is the default
 * language, and a test written against English would pass while the shipped
 * default said something else entirely.
 */

const t = (key: keyof typeof rw, vars: Record<string, string | number> = {}) =>
  Object.entries(vars).reduce<string>(
    (out, [name, value]) => out.replace(`{${name}}`, String(value)),
    rw[key],
  )

// Typed explicitly: inferred from the literals, `etaMinutes` would be `number`
// and the null cases - the ones that matter most here - would not typecheck.
const base: QueuePositionDisplayProps = {
  position: 8,
  etaMinutes: 25,
  leaveHomeBy: "10:15",
  totalAhead: 7,
  totalSeen: 12,
  updatedAt: new Date(),
}

const renderWith = (props: Partial<typeof base>) =>
  render(
    <I18nProvider>
      <QueuePositionDisplay {...base} {...props} />
    </I18nProvider>,
  )

describe("QueuePositionDisplay", () => {
  it("shows the position at display size", () => {
    renderWith({})

    // 72px, weight 900 - readable at arm's length across a waiting room.
    expect(screen.getByText("8")).toHaveClass("text-display")
  })

  it("says the wait is unavailable rather than inventing one", () => {
    renderWith({ etaMinutes: null })

    expect(screen.getByText(t("queue_eta_unknown"))).toBeInTheDocument()
    // No estimate, no "calculating", no fallback anywhere on screen.
    expect(
      screen.queryByText(t("queue_eta_about", { minutes: 25 })),
    ).not.toBeInTheDocument()
  })

  it("hides the departure line entirely when it is not known", () => {
    renderWith({ leaveHomeBy: null })

    // Not an empty row, not a dash - absent. A blank where a time belongs
    // reads as a loading state that never resolves.
    expect(
      screen.queryByText(t("queue_leave_by", { time: "10:15" })),
    ).not.toBeInTheDocument()
  })

  it("shows the departure time when it is known", () => {
    renderWith({})

    expect(
      screen.getByText(t("queue_leave_by", { time: "10:15" })),
    ).toBeInTheDocument()
  })

  it("warns when the number on screen has gone stale", () => {
    renderWith({ updatedAt: new Date(Date.now() - 5 * 60 * 1000) })

    // A queue position that has stopped updating looks exactly like one that
    // has not, so it has to say its own age.
    expect(
      screen.getByText(t("queue_updated_ago", { minutes: 5 })),
    ).toBeInTheDocument()
  })

  it("says nothing about staleness while the data is fresh", () => {
    renderWith({ updatedAt: new Date(Date.now() - 30 * 1000) })

    expect(
      screen.queryByText(t("queue_updated_ago", { minutes: 0 })),
    ).not.toBeInTheDocument()
  })
})
