import { useEffect, useRef, useState } from "react"
import type { StaffService } from "../api/client"

type Props = {
  services: StaffService[]
  onCheckIn: (payload: {
    service: string
    phone?: string
    walk_in_name?: string
  }) => Promise<unknown>
}

/**
 * The screen that decides whether MediLink succeeds.
 *
 * Our competitor is a paper register and an overwhelmed receptionist. Target
 * is under 10 seconds and under 4 keystrokes per patient, so: focus starts
 * here, Enter submits, focus returns here afterwards, and there is no
 * confirmation dialog.
 */
export function CheckInForm({ services, onCheckIn }: Props) {
  const [service, setService] = useState(services[0]?.code ?? "")
  const [walkIn, setWalkIn] = useState(false)
  const [value, setValue] = useState("")
  const [busy, setBusy] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!service && services.length) setService(services[0].code)
  }, [services, service])

  // Focus starts in the input and returns to it after every check-in, so the
  // receptionist never needs the mouse on the common path.
  useEffect(() => {
    inputRef.current?.focus()
  }, [walkIn])

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    const trimmed = value.trim()
    if (!trimmed || !service) return

    setBusy(true)
    await onCheckIn(
      walkIn
        ? { service, walk_in_name: trimmed }
        : { service, phone: trimmed },
    )
    setBusy(false)
    setValue("")
    inputRef.current?.focus()
  }

  return (
    <form onSubmit={submit} className="ml-card p-4">
      <div className="flex flex-wrap items-end gap-3">
        <label className="min-w-48 flex-1">
          <span className="mb-1 block text-small text-ink-muted">Service</span>
          <select
            className="ml-field"
            value={service}
            onChange={(e) => setService(e.target.value)}
          >
            {services.map((s) => (
              <option key={s.code} value={s.code}>
                {s.name_en}
              </option>
            ))}
          </select>
        </label>

        <label className="min-w-64 flex-[2]">
          <span className="mb-1 block text-small text-ink-muted">
            {walkIn ? "Patient name" : "Phone number"}
          </span>
          <input
            ref={inputRef}
            className="ml-field"
            inputMode={walkIn ? "text" : "tel"}
            placeholder={walkIn ? "Uwase Alice" : "078..."}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            autoComplete="off"
          />
        </label>

        <button type="submit" className="ml-btn-primary px-6" disabled={busy || !value.trim()}>
          Check in
        </button>
      </div>

      <label className="mt-3 flex items-center gap-2 text-small">
        <input
          type="checkbox"
          className="ml-checkbox"
          checked={walkIn}
          onChange={(e) => {
            setWalkIn(e.target.checked)
            setValue("")
          }}
        />
        Walk-in, no phone
      </label>
    </form>
  )
}
