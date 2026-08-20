import { describe, expect, it } from "vitest"
import rw from "./rw.json"
import en from "./en.json"
import fr from "./fr.json"

/**
 * Translation integrity.
 *
 * The CI job checks key parity too, but it runs on a machine that may never
 * run. These assertions travel with the code.
 */

const BUNDLES = { rw, en, fr } as Record<string, Record<string, string>>

// Kinyarwanda runs roughly 40% longer than English, and layouts are designed
// to survive that. A RATIO is only meaningful once the English string is long
// enough for it to mean something: "Back" -> "Subira inyuma" is 3.25x and
// entirely fine on a button. So short strings get an absolute cap instead.
const EXPANSION_BUDGET = 2.2
const RATIO_APPLIES_ABOVE = 12 // English characters
const SHORT_STRING_CAP = 24 // characters, for anything below that

describe("translations", () => {
  it("has identical keys in all three languages", () => {
    const base = Object.keys(rw).sort()
    expect(Object.keys(en).sort()).toEqual(base)
    expect(Object.keys(fr).sort()).toEqual(base)
  })

  it("has no empty strings", () => {
    for (const [lang, bundle] of Object.entries(BUNDLES)) {
      for (const [key, value] of Object.entries(bundle)) {
        expect(value.trim(), `${lang}.${key} is empty`).not.toBe("")
      }
    }
  })

  it("uses the same placeholders in every language", () => {
    // A missing placeholder prints a literal {brace} on a patient's screen.
    const placeholders = (s: string) =>
      (s.match(/\{(\w+)\}/g) ?? []).sort().join(",")

    for (const key of Object.keys(rw)) {
      const expected = placeholders(BUNDLES.rw[key])
      for (const lang of ["en", "fr"]) {
        expect(placeholders(BUNDLES[lang][key]), `${lang}.${key}`).toBe(expected)
      }
    }
  })

  it("keeps Kinyarwanda within the layout expansion budget", () => {
    for (const key of Object.keys(rw)) {
      const source = BUNDLES.en[key]
      const target = BUNDLES.rw[key]

      if (source.length >= RATIO_APPLIES_ABOVE) {
        const ratio = target.length / source.length
        expect(
          ratio,
          `rw.${key} is ${ratio.toFixed(1)}x the English`,
        ).toBeLessThan(EXPANSION_BUDGET)
      } else {
        expect(
          target.length,
          `rw.${key} is ${target.length} chars for a short label`,
        ).toBeLessThanOrEqual(SHORT_STRING_CAP)
      }
    }
  })
})
