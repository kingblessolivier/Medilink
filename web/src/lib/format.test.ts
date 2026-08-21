import { describe, expect, it } from "vitest"
import { formatDistance, roundTo5 } from "./format"

describe("roundTo5", () => {
  it("rounds to the nearest five minutes", () => {
    // "43 minutes" implies a precision we do not have; "45" reads as an
    // estimate, which is what it is.
    expect(roundTo5(43)).toBe(45)
    expect(roundTo5(41)).toBe(40)
  })

  it("never returns zero", () => {
    // "About 0 min" on a screen would read as "go now" to a patient who is
    // still eighth in the queue.
    expect(roundTo5(0)).toBe(5)
    expect(roundTo5(1)).toBe(5)
  })
})

describe("formatDistance", () => {
  it("collapses very short distances to a word", () => {
    expect(formatDistance(40, "nearby")).toBe("nearby")
  })

  it("rounds metres to the nearest fifty", () => {
    // GPS is not accurate to the metre, so displaying metres would be a
    // precision claim we cannot support.
    expect(formatDistance(437, "nearby")).toBe("450 m")
  })

  it("switches to kilometres with one decimal", () => {
    expect(formatDistance(5800, "nearby")).toBe("5.8 km")
  })
})
