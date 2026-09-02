import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { Card } from "./Card"

describe("Card", () => {
  it("applies a distinct class for each variant", () => {
    const variants = ["default", "interactive", "selected", "danger"] as const
    const seen = new Set<string>()

    for (const variant of variants) {
      const { unmount } = render(
        <Card variant={variant}>
          <span>content</span>
        </Card>,
      )
      const card = screen.getByText("content").parentElement
      expect(card).toHaveClass("rounded-lg", "border")
      seen.add(card!.className)
      unmount()
    }

    expect(seen.size).toBe(4)
  })

  it("gives the interactive variant a shadow that changes on hover", () => {
    render(
      <Card variant="interactive">
        <span>content</span>
      </Card>,
    )

    const card = screen.getByText("content").parentElement
    // At rest it is barely there - it exists so the hover has somewhere to
    // move from.
    expect(card).toHaveClass("shadow-sm", "hover:shadow-md")
  })

  it("marks the selected variant by weight as well as by hue", () => {
    render(
      <Card variant="selected">
        <span>content</span>
      </Card>,
    )

    // 1.5px, not 1px. At the same weight as an unselected card the only
    // difference left is colour, which is exactly the cue a colour-blind user
    // does not get.
    expect(screen.getByText("content").parentElement).toHaveClass(
      "border-[1.5px]",
      "border-primary",
    )
  })

  it("adds no padding unless asked, so call sites can set their own", () => {
    const { rerender } = render(
      <Card className="p-4">
        <span>content</span>
      </Card>,
    )
    expect(screen.getByText("content").parentElement).toHaveClass("p-4")

    rerender(
      <Card padding="md" className="p-4">
        <span>content</span>
      </Card>,
    )
    expect(screen.getByText("content").parentElement).toHaveClass("p-6")
  })

  it("renders as the requested element", () => {
    render(
      <Card as="article">
        <span>content</span>
      </Card>,
    )

    expect(screen.getByRole("article")).toBeInTheDocument()
  })
})

describe("Card legacy prop", () => {
  it("maps interactive={true} to the interactive variant", () => {
    render(
      <Card interactive>
        <span>content</span>
      </Card>,
    )

    expect(screen.getByText("content").parentElement).toHaveClass("shadow-sm")
  })

  it("never leaks `interactive` into the DOM", () => {
    // It used to fall through `...rest` onto the element: React warned about a
    // non-boolean attribute, and the card lost the hover it was asking for.
    render(
      <Card interactive>
        <span>content</span>
      </Card>,
    )

    expect(
      screen.getByText("content").parentElement,
    ).not.toHaveAttribute("interactive")
  })
})
