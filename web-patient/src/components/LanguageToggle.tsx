import { LANGUAGES, useI18n, type Language } from "../i18n"

/**
 * Lives on the home screen, not buried in settings: Kinyarwanda-first users
 * must not have to hunt for it.
 */
export function LanguageToggle() {
  const { lang, setLang } = useI18n()

  return (
    <div className="flex gap-1" role="group" aria-label="Language">
      {LANGUAGES.map((code: Language) => (
        <button
          key={code}
          onClick={() => setLang(code)}
          aria-pressed={lang === code}
          // 36x26 before this: below any usable touch target, on a control
          // that appears on every screen and is the FIRST thing a Kinyarwanda
          // speaker looking at an English page needs to hit.
          className={
            "inline-flex min-h-touch min-w-touch items-center justify-center " +
            "rounded-lg px-3 text-caption font-medium uppercase " +
            (lang === code
              ? "bg-primary text-white"
              : "bg-surface text-ink-muted border border-line")
          }
        >
          {code}
        </button>
      ))}
    </div>
  )
}
