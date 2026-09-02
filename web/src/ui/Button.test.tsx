import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import { Button } from "./Button"

/**
 * These test the two things a button can get wrong that cost a patient
 * something real: submitting twice on a slow connection, and moving out from
 * under a thumb that is already travelling towards it.
 */

describe("Button", () => {
  it("renders a spinner while loading", () => {
    const { container } = render(<Button loading>Book</Button>)

    expect(container.querySelector(".animate-spin")).toBeInTheDocument()
    // The spinner is decorative; the busy state is what a screen reader gets.
    expect(screen.getByRole("button")).toHaveAttribute("aria-busy", "true")
  })

  it("is disabled while loading, and does not fire a second time", async () => {
    const onClick = vi.fn()
    const user = userEvent.setup()
    render(
      <Button loading onClick={onClick}>
        Book
      </Button>,
    )

    const button = screen.getByRole("button")
    expect(button).toBeDisabled()

    // The reason the flag exists: a patient on a slow connection taps again
    // when nothing appears to happen, and a second tap books a second
    // appointment.
    await user.click(button)
    expect(onClick).not.toHaveBeenCalled()
  })

  it("keeps the label in the DOM while loading so the width is locked", () => {
    render(<Button loading>Confirm booking</Button>)

    // Present but invisible. `hidden` would collapse the box and the button
    // would resize mid-tap.
    const label = screen.getByText("Confirm booking")
    expect(label).toBeInTheDocument()
    expect(label).toHaveClass("invisible")
  })

  it("renders each variant with its own colour, and none of them bare", () => {
    const variants = ["primary", "secondary", "ghost", "danger"] as const
    const seen = new Set<string>()

    for (const variant of variants) {
      const { unmount } = render(<Button variant={variant}>Go</Button>)
      const className = screen.getByRole("button").className
      expect(className).toContain("rounded-pill")
      seen.add(className)
      unmount()
    }

    // Four variants, four distinct class strings - a variant that silently
    // falls through to another one is the failure this catches.
    expect(seen.size).toBe(4)
  })

  it("meets the 44px touch target at the default size", () => {
    render(<Button>Book</Button>)

    // h-control-md resolves to var(--touch-target), which is 44px. Asserting
    // the class rather than a computed height: jsdom applies no stylesheet,
    // so a pixel assertion here would pass whatever the token said.
    expect(screen.getByRole("button")).toHaveClass("h-control-md")
  })
})
