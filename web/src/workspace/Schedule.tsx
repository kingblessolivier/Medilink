import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api, ApiRequestError } from "../api/client"
import { useSession } from "../hooks/useAuth"
import {
  Button,
  Chip,
  EmptyState,
  ErrorState,
  Field,
  Notice,
  Select,
  TableSkeleton,
  TextInput,
} from "../ui"
import type { ScheduleTemplate } from "../api/types"

/**
 * The facility's own bookable hours.
 *
 * Everything about booking rests on `ScheduleTemplate` - slots are expanded
 * from it on read, capacity is locked on it, and `available_slots` returns
 * nothing without one. It was fully modelled, migrated and tested, and there
 * was no way for a facility to create one. Opening a clinic session meant
 * somebody editing the database on the facility's behalf, which works for one
 * pilot site and not for two.
 *
 * A table, not cards. Seven weekdays of sessions is reference material a
 * manager scans down a column - "what is open on Tuesday" - and a grid of
 * tiles makes that comparison harder, not easier.
 *
 * **Closing is deactivation, never deletion.** A closed session stops new
 * bookings and leaves the patients who already hold one, so the row keeps its
 * upcoming count and stays visible. Deleting it would hide the fact that
 * people are still coming.
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

type Draft = {
  weekday: number
  service: string
  provider: string
  start_time: string
  end_time: string
  slot_minutes: number
  capacity_per_slot: number
}

const BLANK: Draft = {
  weekday: 0,
  service: "",
  provider: "",
  start_time: "08:00",
  end_time: "12:00",
  slot_minutes: 15,
  capacity_per_slot: 1,
}

export function WorkspaceSchedule({ canManage }: { canManage: boolean }) {
  const session = useSession()
  const client = useQueryClient()
  const [draft, setDraft] = useState<Draft | null>(null)
  const [error, setError] = useState<string | null>(null)

  const query = useQuery({
    queryKey: ["staff", "schedule"],
    queryFn: api.schedule,
    staleTime: 60_000,
  })

  const me = useQuery({
    queryKey: ["staff", "me"],
    queryFn: api.staffMe,
    staleTime: 10 * 60_000,
  })

  const refresh = () => {
    client.invalidateQueries({ queryKey: ["staff", "schedule"] })
    setDraft(null)
    setError(null)
  }

  const describe = (err: unknown) =>
    err instanceof ApiRequestError ? err.message : "Something went wrong."

  const create = useMutation({
    mutationFn: (body: Draft) =>
      api.createSchedule({
        ...body,
        // Omitted means the general clinic - the session where staff assign
        // whoever is free, which is how most booking here actually works.
        provider: body.provider || undefined,
        // Required by the wire shape. A session is opened open - closing it
        // is a separate, deliberate act on the row.
        active: true,
      }),
    onSuccess: refresh,
    onError: (err) => setError(describe(err)),
  })

  const toggle = useMutation({
    mutationFn: ({ id, active }: { id: number; active: boolean }) =>
      api.updateSchedule(id, { active }),
    onSuccess: () =>
      client.invalidateQueries({ queryKey: ["staff", "schedule"] }),
    onError: (err) => setError(describe(err)),
  })

  const rows = query.data?.results ?? []
  const services = me.data?.services ?? []
  const open = rows.filter((r) => r.active)
  const weeklyCapacity = open.reduce((n, r) => n + r.slots_per_week, 0)

  return (
    <div>
      <div className="ml-section-head">
        <div>
          <h1 className="text-h2">Schedule</h1>
          <p className="mt-1 text-body text-n700">
            When {session?.facility?.name ?? "this facility"} accepts bookings.
            {open.length > 0 && (
              <>
                {" "}
                {open.length} open{" "}
                {open.length === 1 ? "session" : "sessions"}, about{" "}
                <strong className="text-n900">{weeklyCapacity}</strong>{" "}
                appointments a week.
              </>
            )}
          </p>
        </div>
        {canManage && !draft && (
          <Button variant="primary" size="sm" onClick={() => setDraft(BLANK)}>
            Open a session
          </Button>
        )}
      </div>

      {/* A facility with no sessions is not bookable at all. That is the one
          state on this screen worth interrupting somebody about. */}
      {!query.isLoading && rows.length === 0 && (
        <div className="mb-4">
          <Notice tone="warning">
            This facility has no bookable sessions, so patients cannot book an
            appointment here at all. Open one below.
          </Notice>
        </div>
      )}

      {error && (
        <div className="mb-4">
          <Notice tone="warning">{error}</Notice>
        </div>
      )}

      {draft && (
        <SessionForm
          draft={draft}
          services={services}
          busy={create.isPending}
          onChange={setDraft}
          onCancel={() => {
            setDraft(null)
            setError(null)
          }}
          onSave={() => create.mutate(draft)}
        />
      )}

      {query.isLoading && <TableSkeleton rows={5} />}
      {query.isError && (
        <ErrorState
          title="Could not load the schedule."
          action={
            <Button size="sm" onClick={() => query.refetch()}>
              Try again
            </Button>
          }
        />
      )}

      {rows.length > 0 && (
        <div className="ml-scroller">
          <table className="ml-table">
            <thead>
              <tr>
                <th>Day</th>
                <th>Service</th>
                <th>Clinician</th>
                <th>Hours</th>
                <th>Slot</th>
                <th>Per week</th>
                <th>Booked</th>
                <th>Status</th>
                {canManage && <th aria-label="Actions" />}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <Row
                  key={row.id}
                  row={row}
                  canManage={canManage}
                  busy={toggle.isPending}
                  onToggle={() =>
                    toggle.mutate({ id: row.id, active: !row.active })
                  }
                />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!query.isLoading && rows.length === 0 && !draft && canManage && (
        <EmptyState
          title="No sessions yet"
          body="A session is a recurring block of bookable time — for example, general consultation every Tuesday from 08:00 to 12:00."
          action={
            <Button size="sm" onClick={() => setDraft(BLANK)}>
              Open a session
            </Button>
          }
        />
      )}
    </div>
  )
}

function Row({
  row,
  canManage,
  busy,
  onToggle,
}: {
  row: ScheduleTemplate
  canManage: boolean
  busy: boolean
  onToggle: () => void
}) {
  return (
    <tr>
      <td>{WEEKDAYS[row.weekday] ?? row.weekday}</td>
      <td>{row.service_name_en}</td>
      {/* Not blank: "General clinic" is a real answer and an empty cell reads
          as missing data. */}
      <td className="text-n700">{row.provider_name ?? "General clinic"}</td>
      <td className="tabular-nums">
        {row.start_time}–{row.end_time}
      </td>
      <td className="tabular-nums">
        {row.slot_minutes} min
        {row.capacity_per_slot > 1 && ` ×${row.capacity_per_slot}`}
      </td>
      <td className="tabular-nums">{row.slots_per_week}</td>
      {/* The number that matters before closing a session: it stops new
          bookings and does NOT cancel these. */}
      <td className="tabular-nums">
        {row.upcoming > 0 ? (
          <strong className="text-n900">{row.upcoming}</strong>
        ) : (
          <span className="text-n600">0</span>
        )}
      </td>
      <td>
        <Chip tone={row.active ? "success" : "neutral"}>
          {row.active ? "Open" : "Closed"}
        </Chip>
      </td>
      {canManage && (
        <td>
          <Button
            size="sm"
            variant={row.active ? "secondary" : "primary"}
            disabled={busy}
            onClick={onToggle}
          >
            {row.active ? "Close" : "Reopen"}
          </Button>
          {row.active && row.upcoming > 0 && (
            <p className="mt-1 text-label text-n700">
              {row.upcoming} still booked
            </p>
          )}
        </td>
      )}
    </tr>
  )
}

function SessionForm({
  draft,
  services,
  busy,
  onChange,
  onCancel,
  onSave,
}: {
  draft: Draft
  services: { code: string; name_en: string }[]
  busy: boolean
  onChange: (d: Draft) => void
  onCancel: () => void
  onSave: () => void
}) {
  const set = <K extends keyof Draft>(key: K, value: Draft[K]) =>
    onChange({ ...draft, [key]: value })

  // Mirrors the server's arithmetic so somebody sees the consequence of
  // "15 minutes, 2 per slot" before they commit to it.
  const span =
    (Number(draft.end_time.slice(0, 2)) * 60 +
      Number(draft.end_time.slice(3, 5))) -
    (Number(draft.start_time.slice(0, 2)) * 60 +
      Number(draft.start_time.slice(3, 5)))
  const perWeek =
    span > 0 && draft.slot_minutes > 0
      ? Math.floor(span / draft.slot_minutes) * draft.capacity_per_slot
      : 0

  return (
    <form
      className="mb-6 rounded-md border border-n200 bg-white p-4"
      onSubmit={(e) => {
        e.preventDefault()
        onSave()
      }}
    >
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <Field label="Day">
          {(id) => (
            <Select
              id={id}
              value={String(draft.weekday)}
              onChange={(e) => set("weekday", Number(e.target.value))}
            >
              {WEEKDAYS.map((day, index) => (
                <option key={day} value={index}>
                  {day}
                </option>
              ))}
            </Select>
          )}
        </Field>

        <Field label="Service">
          {(id) => (
            <Select
              id={id}
              value={draft.service}
              onChange={(e) => set("service", e.target.value)}
            >
              <option value="">Choose a service</option>
              {services.map((s) => (
                <option key={s.code} value={s.code}>
                  {s.name_en}
                </option>
              ))}
            </Select>
          )}
        </Field>

        <Field
          label="Clinician"
          hint="Leave blank for the general clinic, where staff assign whoever is free."
        >
          {(id, describedBy) => (
            <TextInput
              id={id}
              aria-describedby={describedBy}
              placeholder="Optional"
              value={draft.provider}
              onChange={(e) => set("provider", e.target.value)}
            />
          )}
        </Field>

        <Field label="Starts">
          {(id) => (
            <TextInput
              id={id}
              type="time"
              value={draft.start_time}
              onChange={(e) => set("start_time", e.target.value)}
            />
          )}
        </Field>

        <Field label="Ends">
          {(id) => (
            <TextInput
              id={id}
              type="time"
              value={draft.end_time}
              onChange={(e) => set("end_time", e.target.value)}
            />
          )}
        </Field>

        <Field label="Minutes per appointment">
          {(id) => (
            <TextInput
              id={id}
              type="number"
              min={5}
              max={240}
              value={String(draft.slot_minutes)}
              onChange={(e) => set("slot_minutes", Number(e.target.value))}
            />
          )}
        </Field>

        <Field
          label="Patients per slot"
          hint="More than one where several clinicians run the same session."
        >
          {(id, describedBy) => (
            <TextInput
              id={id}
              aria-describedby={describedBy}
              type="number"
              min={1}
              max={50}
              value={String(draft.capacity_per_slot)}
              onChange={(e) => set("capacity_per_slot", Number(e.target.value))}
            />
          )}
        </Field>
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-n200 pt-4">
        <p className="text-body text-n700">
          {perWeek > 0 ? (
            <>
              This opens{" "}
              <strong className="text-n900 tabular-nums">{perWeek}</strong>{" "}
              appointments every {WEEKDAYS[draft.weekday]}.
            </>
          ) : (
            "Set an end time after the start time."
          )}
        </p>
        <div className="flex gap-2">
          <Button type="button" variant="ghost" size="sm" onClick={onCancel}>
            Cancel
          </Button>
          <Button
            variant="primary"
            size="sm"
            loading={busy}
            disabled={!draft.service || perWeek <= 0}
          >
            Open session
          </Button>
        </div>
      </div>
    </form>
  )
}
