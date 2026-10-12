import { fireEvent, render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { expect, it } from "vitest"
import { I18nProvider } from "../i18n"
import { DashboardShell } from "./DashboardShell"

it("collapses and expands dashboard destinations without a horizontal menu", () => {
  render(<I18nProvider><MemoryRouter initialEntries={["/workspace"]}><DashboardShell title="Ahakorerwa" sections={[{ label: "Uyu munsi", items: [{ to: "/workspace", label: "Kwakira abarwayi", icon: null, end: true }, { to: "/workspace/security", label: "Umutekano wa konti", icon: null }] }]}><p>Dashboard</p></DashboardShell></MemoryRouter></I18nProvider>)
  const toggle = screen.getByRole("button", { name: "Kwakira abarwayi" })
  expect(toggle).toHaveAttribute("aria-expanded", "false")
  fireEvent.click(toggle)
  expect(toggle).toHaveAttribute("aria-expanded", "true")
  const link = screen.getByRole("link", { name: "Umutekano wa konti" })
  expect(link).toHaveClass("min-h-touch")
  fireEvent.click(link)
  expect(toggle).toHaveAttribute("aria-expanded", "false")
})
