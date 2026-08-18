import { createContext, useContext, useEffect, useState, type ReactNode } from "react"
import rw from "./rw.json"
import en from "./en.json"
import fr from "./fr.json"

export const LANGUAGES = ["rw", "en", "fr"] as const
export type Language = (typeof LANGUAGES)[number]

export const LANGUAGE_LABELS: Record<Language, string> = {
  rw: "Kinyarwanda",
  en: "English",
  fr: "Francais",
}

const BUNDLES: Record<Language, Record<string, string>> = { rw, en, fr }

// Kinyarwanda is the default, not an afterthought.
const DEFAULT_LANGUAGE: Language = "rw"
const STORAGE_KEY = "medilink.language"

type Vars = Record<string, string | number>

type I18nValue = {
  lang: Language
  setLang: (lang: Language) => void
  t: (key: string, vars?: Vars) => string
}

const I18nContext = createContext<I18nValue | null>(null)

function interpolate(template: string, vars?: Vars): string {
  if (!vars) return template
  // Interpolation, never concatenation of translated fragments - word order
  // differs between the three languages.
  return template.replace(/\{(\w+)\}/g, (_, name) =>
    name in vars ? String(vars[name]) : `{${name}}`,
  )
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Language>(() => {
    const stored = localStorage.getItem(STORAGE_KEY)
    return LANGUAGES.includes(stored as Language)
      ? (stored as Language)
      : DEFAULT_LANGUAGE
  })

  useEffect(() => {
    document.documentElement.lang = lang
  }, [lang])

  const setLang = (next: Language) => {
    localStorage.setItem(STORAGE_KEY, next)
    setLangState(next)
  }

  const t = (key: string, vars?: Vars) => {
    const template = BUNDLES[lang][key] ?? BUNDLES[DEFAULT_LANGUAGE][key] ?? key
    return interpolate(template, vars)
  }

  return (
    <I18nContext.Provider value={{ lang, setLang, t }}>
      {children}
    </I18nContext.Provider>
  )
}

export function useI18n(): I18nValue {
  const value = useContext(I18nContext)
  if (!value) throw new Error("useI18n must be used inside I18nProvider")
  return value
}
