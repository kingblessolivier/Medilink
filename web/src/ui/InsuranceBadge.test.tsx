import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import en from "../i18n/en.json"
import fr from "../i18n/fr.json"
import rw from "../i18n/rw.json"
import { I18nProvider } from "../i18n"
import { InsuranceBadge } from "./InsuranceBadge"

/**
 * The copy rule, enforced in every language.
 *
 * MediLink knows what a facility says it accepts. Whether a given patient's
 * membership is active is a different question, answered by a system this
 * product is not integrated with. A patient turned away at a desk after
 * reading "you are covered" here does not make that distinction for us.
 *
 * Rendered assertions run against Kinyarwanda, the default language.
 */

const renderWith = (props: Parameters<typeof InsuranceBadge>[0]) =>
  render(
    <I18nProvider>
      <InsuranceBadge {...props} />
    </I18nProvider>,
  )

describe("InsuranceBadge", () => {
  it("says the facility accepts the insurer", () => {
    renderWith({ status: "accepted", insurerName: "Mutuelle" })

    expect(
      screen.getByText(rw.accepts_insurer.replace("{insurer}", "Mutuelle")),
    ).toBeInTheDocument()
  })

  it("states plainly when an insurer is not accepted", () => {
    renderWith({ status: "not-accepted", insurerName: "Mutuelle" })

    expect(
      screen.getByText(rw.not_accepts_insurer.replace("{insurer}", "Mutuelle")),
    ).toBeInTheDocument()
  })

  it("says the status is unknown rather than assuming either way", () => {
    renderWith({ status: "unknown", insurerName: "Mutuelle" })

    expect(screen.getByText(rw.insurance_status_unknown)).toBeInTheDocument()
  })

  it("never claims a patient is covered, in any language", () => {
    // Asserted on the three keys this badge can render, not across the whole
    // bundle. The disclaimers elsewhere say "never that you are covered" on
    // purpose - a blanket scan flags the very strings that state the rule.
    const RENDERED = [
      "accepts_insurer",
      "not_accepts_insurer",
      "insurance_status_unknown",
    ] as const

    // "Covered" in each language. If one of these ever appears in the badge
    // itself, the product is making a promise it cannot keep.
    const claim = /cover|couvert|wishyuriwe/i

    for (const bundle of [rw, en, fr] as Array<Record<string, string>>) {
      for (const key of RENDERED) {
        expect(bundle[key]).toBeTruthy()
        expect(bundle[key]).not.toMatch(claim)
      }
    }
  })
})
