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
        className="inline-flex h-touch items-center gap-1.5 rounded-md border border-n200 bg-white px-2.5 text-label uppercase text-n700 sm:hidden"
      >
        <IconGlobe size={16} />
        {lang}
      </button>

      {/* Wide: all three, so the choice is visible rather than discovered. */}
      <div
        className="hidden rounded-md border border-n200 bg-n100 p-0.5 sm:flex"
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
            // One bordered group, not three separate buttons. Three boxed
            // controls with a solid green fill on the current one put a
            // saturated brand-coloured block in the top bar of every screen,
            // competing with Sign in. A segmented control reads as one
            // setting, and the selected segment only needs a surface lift.
            className={
              "inline-flex min-h-touch min-w-touch items-center justify-center " +
              "rounded-md px-2.5 text-label uppercase transition-colors " +
              (lang === code
                ? "bg-white text-n900 shadow-sm"
                : "text-n600 hover:text-n900")
            }
          >
            {code}
          </button>
        ))}
      </div>
    </>
  )
}
