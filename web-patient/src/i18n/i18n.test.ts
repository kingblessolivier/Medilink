import { describe, expect, it } from "vitest"
import en from "./en.json"
import fr from "./fr.json"
import rw from "./rw.json"

/**
 * This was a `node -e` script inlined in .github/workflows/ci.yml, which meant
 * it could only run in CI. A missing key falls back to the key itself, so the
 * screen reads "wait_unavailable" to a patient - it should be catchable before
 * pushing.
 */

const BUNDLES = { rw, en, fr } as const
const PLACEHOLDER = /\{(\w+)\}/g

function placeholders(value: string): Set<string> {
  return new Set([...value.matchAll(PLACEHOLDER)].map((m) => m[1]))
}

describe("translation bundles", () => {
  const base = Object.keys(rw).sort()

  it.each(["en", "fr"] as const)("%s has exactly the same keys as rw", (lang) => {
    expect(Object.keys(BUNDLES[lang]).sort()).toEqual(base)
  })

  it.each(["rw", "en", "fr"] as const)("%s has no empty strings", (lang) => {
    const empty = Object.entries(BUNDLES[lang])
      .filter(([, value]) => value.trim() === "")
      .map(([key]) => key)
    expect(empty).toEqual([])
  })

  it.each(["en", "fr"] as const)(
    "%s uses the same interpolation variables as rw",
    (lang) => {
      const mismatched: string[] = []
      for (const key of base) {
        const expected = placeholders(rw[key as keyof typeof rw])
        const actual = placeholders(BUNDLES[lang][key as keyof typeof en])
        if (
          expected.size !== actual.size ||
          [...expected].some((name) => !actual.has(name))
        ) {
          mismatched.push(key)
        }
      }
      // A translation that drops {minutes} renders a sentence with the number
      // missing; one that invents {min} renders a literal brace to the patient.
      expect(mismatched).toEqual([])
    },
  )

  it("is not empty, so the assertions above cannot pass vacuously", () => {
    expect(base.length).toBeGreaterThan(20)
  })
})
