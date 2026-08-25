import { render, screen, act } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { ProgressSteps } from "./ProgressSteps"

/**
 * The point of these tests is the pacing, not the markup.
 *
 * The brief asks the Care Guide to say what it is doing rather than
 * "Loading…". The risk in obliging is theatre: the triage engine is a
 * deterministic lookup with no inference, so a scripted four-second sequence
 * would be inventing work to look intelligent. These assert that later steps
 * appear only as time actually passes.
 */

const STEPS = ["Reviewing your answers", "Checking care pathways", "Finding care"]

describe("ProgressSteps", () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it("shows only the first step immediately", () => {
    render(<ProgressSteps steps={STEPS} />)

    expect(screen.getByText(STEPS[0])).toBeInTheDocument()
    expect(screen.queryByText(STEPS[1])).not.toBeInTheDocument()
  })

  it("advances only as the request keeps running", () => {
    render(<ProgressSteps steps={STEPS} />)

    act(() => void vi.advanceTimersByTime(1000))
    expect(screen.getByText(STEPS[1])).toBeInTheDocument()

    act(() => void vi.advanceTimersByTime(1000))
    expect(screen.getByText(STEPS[2])).toBeInTheDocument()
  })

  it("stops at the last step rather than cycling", () => {
    render(<ProgressSteps steps={STEPS} />)

    // Each step schedules the next only after it renders, so time is advanced
    // one step at a time - a single large jump fires only the timer that was
    // already pending.
    act(() => void vi.advanceTimersByTime(1000))
    act(() => void vi.advanceTimersByTime(1000))
    act(() => void vi.advanceTimersByTime(60_000))

    // Still the last one, and each earlier step listed exactly once.
    expect(screen.getAllByText(STEPS[2])).toHaveLength(1)
    expect(screen.getAllByText(STEPS[0])).toHaveLength(1)
  })

  it("announces itself politely to a screen reader", () => {
    render(<ProgressSteps steps={STEPS} />)

    const live = screen.getByRole("status")
    expect(live).toHaveAttribute("aria-live", "polite")
  })
})
