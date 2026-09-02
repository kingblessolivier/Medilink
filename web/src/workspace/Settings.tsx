import { useEffect, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api, ApiRequestError } from "../api/client"
import {
  Button,
  Chip,
  ErrorState,
  Field,
  Notice,
  TableSkeleton,
  TextInput,
} from "../ui"

/**
 * What a facility may change about itself.
 *
 * Editable: how to reach it, and when it is open. Those change often, the
 * facility is the only one who knows, and a wrong phone number is a patient
 * who cannot ring ahead.
 *
 * **Not editable: name, level, ownership, district.** Those are what
 * `verified_at` attests to, and a facility that could rename itself or move
 * its own pin would be editing the thing MediLink checked. They are shown
 * read-only so a manager can see what was verified, with the route to change
 * them stated rather than hidden.
 *
 * Hours are replaced as a whole week rather than patched row by row: a
 * weekday can hold two periods, which is how a lunch break is modelled and
 * how a health centre actually runs, so there is no stable "the Tuesday row".
 */

const WEEKDAYS = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
]

type HourRow = { weekday: number; opens_at: string; closes_at: string }

export function WorkspaceSettings({ canManage }: { canManage: boolean }) {
  const client = useQueryClient()
  const [contact, setContact] = useState({
    phone: "",
    email: "",
    address: "",
    sector: "",
  })
  const [hours, setHours] = useState<HourRow[]>([])
  const [saved, setSaved] = useState<string | null>(null)

  const query = useQuery({
    queryKey: ["staff", "facility"],
    queryFn: api.facilitySettings,
    staleTime: 60_000,
  })

  // Seed the form once the server answers. Not `initialData` - a stale draft
  // silently overwriting a colleague's edit is worse than a blank field.
  useEffect(() => {
    if (!query.data) return
    setContact({
      phone: query.data.phone ?? "",
      email: query.data.email ?? "",
      address: query.data.address ?? "",
      sector: query.data.sector ?? "",
    })
    setHours(query.data.hours ?? [])
  }, [query.data])

  const invalidate = () => {
    client.invalidateQueries({ queryKey: ["staff", "facility"] })
    setSaved("Saved.")
    setTimeout(() => setSaved(null), 2500)
  }

  const saveContact = useMutation({
    mutationFn: () => api.updateFacilityContact(contact),
    onSuccess: invalidate,
  })

  const saveHours = useMutation({
    mutationFn: () => api.replaceOpeningHours({ hours }),
    onSuccess: invalidate,
  })

  const failure = saveContact.error ?? saveHours.error
  const facility = query.data

  const addPeriod = (weekday: number) =>
    setHours((rows) =>
      [...rows, { weekday, opens_at: "08:00", closes_at: "12:00" }].sort(
        (a, b) =>
          a.weekday - b.weekday || a.opens_at.localeCompare(b.opens_at),
      ),
    )

  const removePeriod = (index: number) =>
    setHours((rows) => rows.filter((_, i) => i !== index))

  const editPeriod = (index: number, patch: Partial<HourRow>) =>
    setHours((rows) =>
      rows.map((row, i) => (i === index ? { ...row, ...patch } : row)),
    )

  return (
    <div>
      <div className="ml-section-head">
        <div>
          <h1 className="text-h2">Facility settings</h1>
          <p className="mt-1 text-body text-n700">
            How patients reach this facility, and when it is open.
          </p>
        </div>
        {saved && <Chip tone="success">{saved}</Chip>}
      </div>

      {failure && (
        <div className="mb-4">
          <Notice tone="warning">
            {failure instanceof ApiRequestError
              ? failure.message
              : "Could not save. Try again."}
          </Notice>
        </div>
      )}

      {query.isLoading && <TableSkeleton rows={4} />}
      {query.isError && (
        <ErrorState
          title="Could not load settings."
          action={
            <Button size="sm" onClick={() => query.refetch()}>
              Try again
            </Button>
          }
        />
      )}

      {facility && (
        <div className="space-y-6">
          {/* What verification attests to. Read-only, and it says why. */}
          <section className="rounded-md border border-n200 bg-n100 p-4">
            <h2 className="text-h3">{facility.name}</h2>
            <p className="mt-1 text-body text-n700">
              {facility.level} · {facility.ownership} · {facility.district}
              {facility.verified && (
                <>
                  {" "}
                  · <span className="text-success">Verified</span>
                </>
              )}
            </p>
            <p className="mt-3 text-body text-n700">
              The name, type and location are part of what MediLink verified,
              so they are not editable here. Contact MediLink to change them.
            </p>
          </section>

          <section>
            <h2 className="text-h3 mb-3">Contact</h2>
            <form
              className="grid gap-3 sm:grid-cols-2"
              onSubmit={(e) => {
                e.preventDefault()
                saveContact.mutate()
              }}
            >
              <Field label="Phone" hint="What a patient rings to ask a question.">
                {(id, describedBy) => (
                  <TextInput
                    id={id}
                    aria-describedby={describedBy}
                    inputMode="tel"
                    disabled={!canManage}
                    value={contact.phone}
                    onChange={(e) =>
                      setContact({ ...contact, phone: e.target.value })
                    }
                  />
                )}
              </Field>
              <Field label="Email">
                {(id) => (
                  <TextInput
                    id={id}
                    type="email"
                    disabled={!canManage}
                    value={contact.email}
                    onChange={(e) =>
                      setContact({ ...contact, email: e.target.value })
                    }
                  />
                )}
              </Field>
              <Field label="Address">
                {(id) => (
                  <TextInput
                    id={id}
                    disabled={!canManage}
                    value={contact.address}
                    onChange={(e) =>
                      setContact({ ...contact, address: e.target.value })
                    }
                  />
                )}
              </Field>
              <Field label="Sector">
                {(id) => (
                  <TextInput
                    id={id}
                    disabled={!canManage}
                    value={contact.sector}
                    onChange={(e) =>
                      setContact({ ...contact, sector: e.target.value })
                    }
                  />
                )}
              </Field>
              {canManage && (
                <div className="sm:col-span-2">
                  <Button
                    variant="primary"
                    size="sm"
                    loading={saveContact.isPending}
                  >
                    Save contact details
                  </Button>
                </div>
              )}
            </form>
          </section>

          <section>
            <h2 className="text-h3 mb-1">Opening hours</h2>
            <p className="mb-3 text-body text-n700">
              These decide whether patients see this facility as open, and
              whether it appears under &ldquo;open now&rdquo;. Add a second
              period on a day to show a lunch break.
            </p>

            {hours.length === 0 && (
              <div className="mb-3">
                <Notice tone="warning">
                  With no opening hours, this facility reads as closed at all
                  times and its waiting times show as unavailable.
                </Notice>
              </div>
            )}

            <div className="space-y-2">
              {WEEKDAYS.map((label, weekday) => {
                const periods = hours
                  .map((row, index) => ({ row, index }))
                  .filter(({ row }) => row.weekday === weekday)
                return (
                  <div
                    key={label}
                    className="flex flex-wrap items-center gap-3 border-b border-n200 py-2"
                  >
                    <span className="w-24 shrink-0 text-body-lg font-medium">
                      {label}
                    </span>
                    {periods.length === 0 && (
                      <span className="text-body text-n700">Closed</span>
                    )}
                    {periods.map(({ row, index }) => (
                      <span key={index} className="flex items-center gap-1.5">
                        <TextInput
                          type="time"
                          aria-label={`${label} opens`}
                          disabled={!canManage}
                          className="w-28"
                          value={row.opens_at}
                          onChange={(e) =>
                            editPeriod(index, { opens_at: e.target.value })
                          }
                        />
                        <span className="text-n700">–</span>
                        <TextInput
                          type="time"
                          aria-label={`${label} closes`}
                          disabled={!canManage}
                          className="w-28"
                          value={row.closes_at}
                          onChange={(e) =>
                            editPeriod(index, { closes_at: e.target.value })
                          }
                        />
                        {canManage && (
                          <Button
                            type="button"
                            size="sm"
                            variant="ghost"
                            onClick={() => removePeriod(index)}
                          >
                            Remove
                          </Button>
                        )}
                      </span>
                    ))}
                    {canManage && (
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        onClick={() => addPeriod(weekday)}
                      >
                        {periods.length === 0 ? "Open this day" : "Add a period"}
                      </Button>
                    )}
                  </div>
                )
              })}
            </div>

            {canManage && (
              <div className="mt-4">
                <Button
                  variant="primary"
                  size="sm"
                  loading={saveHours.isPending}
                  onClick={() => saveHours.mutate()}
                >
                  Save opening hours
                </Button>
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  )
}
