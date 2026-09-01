import { describe, expect, it } from "vitest"
import { formatDistance, roundTo5, timeAgo } from "./format"

describe("formatDistance", () => {
  it("says 'nearby' rather than a false-precision metre count", () => {
    expect(formatDistance(40, "Hafi")).toBe("Hafi")
    expect(formatDistance(99, "Hafi")).toBe("Hafi")
  })

  it("rounds metres to the nearest 50 under a kilometre", () => {
    expect(formatDistance(120, "Hafi")).toBe("100 m")
    expect(formatDistance(175, "Hafi")).toBe("200 m")
    expect(formatDistance(999, "Hafi")).toBe("1000 m")
  })

  it("switches to kilometres at one, with one decimal", () => {
    expect(formatDistance(1000, "Hafi")).toBe("1.0 km")
    expect(formatDistance(4370, "Hafi")).toBe("4.4 km")
    expect(formatDistance(82000, "Hafi")).toBe("82.0 km")
  })
})

describe("roundTo5", () => {
  it("rounds to the nearest five", () => {
    expect(roundTo5(43)).toBe(45)
    expect(roundTo5(41)).toBe(40)
  })

  it("never claims a wait shorter than five minutes", () => {
    // "1 min" reads as a promise. The floor keeps it an estimate.
    expect(roundTo5(0)).toBe(5)
    expect(roundTo5(1)).toBe(5)
    expect(roundTo5(2)).toBe(5)
  })
})

describe("timeAgo", () => {
  const secondsAgo = (n: number) => new Date(Date.now() - n * 1000).toISOString()

  it("reads as 'just now' under a minute, in each language", () => {
    expect(timeAgo(secondsAgo(30), "rw")).toBe("ubu")
    expect(timeAgo(secondsAgo(30), "en")).toBe("just now")
    expect(timeAgo(secondsAgo(30), "fr")).toBe("a l'instant")
  })

  it("puts the unit before the number in Kinyarwanda", () => {
    expect(timeAgo(secondsAgo(300), "rw")).toBe("iminota 5")
    expect(timeAgo(secondsAgo(300), "en")).toBe("5 min")
  })

  it("falls back to English for an unknown language rather than crashing", () => {
    expect(timeAgo(secondsAgo(300), "sw")).toBe("5 min")
  })
})
