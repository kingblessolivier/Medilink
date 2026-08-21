import type { Language } from "../i18n"

/** A specialty as the API now returns it: code plus all three names. */
export type SpecialtyBrief = {
  code: string
  name_rw: string
  name_en: string
  name_fr: string
}

/**
 * The specialty's name in the reader's language.
 *
 * Exists because this used to be done in three places and skipped in two -
 * which is how "general-medicine" ended up on a patient's screen.
 */
export function specialtyName(
  specialty: SpecialtyBrief,
  lang: Language,
): string {
  return lang === "rw"
    ? specialty.name_rw
    : lang === "fr"
      ? specialty.name_fr
      : specialty.name_en
}

export function specialtyNames(
  specialties: SpecialtyBrief[],
  lang: Language,
): string {
  return specialties.map((s) => specialtyName(s, lang)).join(" · ")
}
