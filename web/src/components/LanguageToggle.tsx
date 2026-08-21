import { LANGUAGES, useI18n, type Language } from "../i18n"
import { IconGlobe } from "../ui/icons"

/**
 * In the top bar on every screen, not buried in settings: a Kinyarwanda-first
 * user who lands on an English page must not have to hunt for this.
 *
 * Two shapes for two widths. Three side-by-side buttons is the right control
 * when there is room - the choice is visible and one tap away. At 360px those
 * same three buttons took roughly a third of the bar, on something most
 * people set once, so below `sm` it collapses to a single cycling button
 * showing the current language.
 *
 * Cycling rather than a dropdown: with three options, one tap to advance beats
 * two taps to open and pick, and the full set is visible again the moment the
 * screen is wide enough.
 */
export function LanguageToggle() {
  const { lang, setLang, t } = useI18n()

  const next = LANGUAGES[(LANGUAGES.indexOf(lang) + 1) % LANGUAGES.length]

  return (
    <>
      {/* Narrow: one control. The globe says what it is without a word in a
          language the reader may not have chosen yet. */}
      <button
        onClick={() => setLang(next)}
        // The accessible name has to say what pressing it DOES - "RW" alone
        // tells a screen-reader user nothing about the outcome.
        aria-label={t("switch_language_to", { language: next.toUpperCase() })}
        className="inline-flex h-touch items-center gap-1.5 rounded-lg border border-line bg-surface px-2.5 text-caption font-semibold uppercase text-ink-muted sm:hidden"
      >
        <IconGlobe size={16} />
        {lang}
      </button>

      {/* Wide: all three, so the choice is visible rather than discovered. */}
      <div
        className="hidden gap-1 sm:flex"
        role="group"
        aria-label={t("language")}
      >
        {LANGUAGES.map((code: Language) => (
          <button
            key={code}
            onClick={() => setLang(code)}
            aria-pressed={lang === code}
            // 36x26 before this: below any usable touch target, on a control
            // that appears on every screen.
            className={
              "inline-flex min-h-touch min-w-touch items-center justify-center " +
              "rounded-lg px-3 text-caption font-medium uppercase " +
              (lang === code
                ? "bg-primary text-white"
                : "border border-line bg-surface text-ink-muted")
            }
          >
            {code}
          </button>
        ))}
      </div>
    </>
  )
}
