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
          className={
            "rounded-lg px-2 py-1 text-xs font-medium uppercase " +
            (lang === code
              ? "bg-primary text-white"
              : "bg-white text-neutral-600 border border-neutral-300")
          }
        >
          {code}
        </button>
      ))}
    </div>
  )
}
