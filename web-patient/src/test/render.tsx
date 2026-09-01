import { render } from "@testing-library/react"
import type { ReactElement } from "react"
import { I18nProvider } from "../i18n"

/** Every component under test reads translations, so none render bare. */
export function renderWithI18n(ui: ReactElement, { lang = "rw" } = {}) {
  localStorage.setItem("medilink.language", lang)
  return render(<I18nProvider>{ui}</I18nProvider>)
}
