import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, expect, it, vi } from "vitest"
import { I18nProvider } from "../i18n"
import { api, tokens } from "../api/client"
import { Security } from "./Security"
import type { SignInResponse } from "../api/types"

const reload = vi.hoisted(() => vi.fn().mockResolvedValue(undefined))
vi.mock("../hooks/useAuth", () => ({ useAuth: () => ({ reload }) }))
vi.mock("../api/client", () => ({ api: { changePassword: vi.fn() }, tokens: { save: vi.fn() } }))
beforeEach(() => { vi.clearAllMocks(); localStorage.removeItem("medilink.language") })

function fill(confirm = "New-password-823") {
  render(<I18nProvider><Security /></I18nProvider>)
  fireEvent.change(screen.getByLabelText("Ijambo ry'ibanga ukoresha"), { target: { value: "Old-password-823" } })
  fireEvent.change(screen.getByLabelText("Ijambo ry'ibanga rishya"), { target: { value: "New-password-823" } })
  fireEvent.change(screen.getByLabelText("Emeza ijambo ry'ibanga"), { target: { value: confirm } })
  fireEvent.submit(screen.getByRole("button", { name: "Hindura ijambo ry'ibanga" }).closest("form")!)
}

it("refuses mismatched confirmation in Kinyarwanda", () => {
  fill("different-password")
  expect(screen.getByRole("status")).toHaveTextContent("Amagambo y'ibanga ntahuye.")
  expect(api.changePassword).not.toHaveBeenCalled()
})

it("replaces credentials and reloads the account after a successful change", async () => {
  vi.mocked(api.changePassword).mockResolvedValue({ access: "new-access", refresh: "new-refresh" } as SignInResponse)
  fill()
  await waitFor(() => expect(tokens.save).toHaveBeenCalledWith("new-access", "new-refresh"))
  expect(reload).toHaveBeenCalled()
  expect(screen.getByLabelText("Ijambo ry'ibanga rishya")).toHaveValue("")
})
