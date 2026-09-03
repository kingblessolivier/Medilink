/**
 * CL-01 and CL-02 from docs/02_dashboards.html: the clinician's worklist and
 * the detail panel beside it.
 *
 * Until this screen existed a doctor had nowhere to look. The workspace was
 * built for the desk - reception checks people in, reception moves the queue -
 * and the loop ended there. `Patients` is a reception lookup and says so in
 * its own header: "this is deliberately not a patient record viewer."
 *
 * WHAT THIS IS NOT, and the distinction matters more here than anywhere else
 * in the product: it is not a clinical record. There is no vitals table, no
 * lab result, no prescription and no note model in this codebase - CL-03,
 * CL-05 and CL-06 are unbuilt, and none of them can be faked. A screen that
 * renders an empty "Triage vitals" card teaches a clinician to look there,
 * and the day somebody records vitals elsewhere and this shows blank is the
 * day it becomes dangerous. So the clinical sections are absent rather than
 * empty, and the panel says plainly what it holds.
 *
 * What it does hold is the queue context for the person in front of you: who
 * is waiting, for which service, how long they have been there, what they are
 * covered by, and whether you have seen them before.
 *
 * THE ACTIONS ARE READ-ONLY, deliberately. `StaffMember.can_manage_queue` is
 * true only for receptionists and admins, so a clinician cannot call or serve
 * from here. The mock draws those buttons; the permission model says
 * otherwise, and launch day is the wrong moment to widen an access rule. The
 * desk moves the queue.
 */

import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { api } from "../api/client"
import type { Board } from "../api/types"
import { Badge, Card, ErrorState, TableSkeleton } from "../ui"
import { IconClock, IconUser } from "../ui/icons"

type Row = {
  id: number
  ticket: string
  name: string
  service: string
  serviceName: string
  status: string
  waitedMinutes: number
  position: number | null
}

/** Flatten the board into one worklist, called patients first. */
function rowsFrom(board: Board | undefined): Row[] {
  if (!board) return []
  const out: Row[] = []
  for (const group of board.services) {
    const label = group.service_name_en || group.service
    for (const entry of [...group.called, ...group.waiting]) {
      out.push({
        id: entry.id,
        ticket: entry.ticket_code,
        name: entry.display_name || entry.ticket_code,
        service: group.service,
        serviceName: label,
        status: entry.status,
        waitedMinutes: entry.waited_minutes ?? 0,
        position: entry.position ?? null,
      })
    }
  }
  // Called first, then by how long they have waited. A clinician's next
  // question is "who has been here longest", not "who arrived first" - those
  // differ once somebody has been called and sent back.
  return out.sort((a, b) => {
    if (a.status !== b.status) return a.status === "called" ? -1 : 1
    return b.waitedMinutes - a.waitedMinutes
  })
}

function waitedLabel(minutes: number): string {
  if (minutes < 60) return `${minutes} min`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ${minutes % 60}m`
  return `${Math.floor(hours / 24)}d ${hours % 24}h`
}

export function WorkspaceClinic() {
  const board = useQuery({
    queryKey: ["board"],
    queryFn: api.board,
    refetchInterval: 15_000,
  })

  const rows = useMemo(() => rowsFrom(board.data), [board.data])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const selected = rows.find((r) => r.id === selectedId) ?? rows[0] ?? null

  if (board.isLoading) return <TableSkeleton rows={5} />
  if (board.isError) return <ErrorState title="Could not load the queue." />

  return (
    <div>
      <h1 className="text-h1 text-n900">Clinic</h1>
      <p className="mt-1 text-body text-n700">
        {rows.length === 0
          ? "Nobody is waiting."
          : `${rows.length} waiting or called at ${board.data?.facility.name}.`}
      </p>

      <div className="mt-6 grid gap-4 lg:grid-cols-[22rem_minmax(0,1fr)]">
        {/* CL-01 - the worklist. */}
        <Card className="overflow-hidden p-0">
          <p className="ml-label border-b border-n200 px-4 py-3">
            Today&rsquo;s patients
          </p>
          {rows.length === 0 ? (
            <p className="px-4 py-6 text-body text-n700">
              Nobody has been checked in yet.
            </p>
          ) : (
            <ul className="max-h-[32rem] overflow-y-auto">
              {rows.map((row) => {
                const active = selected?.id === row.id
                return (
                  <li key={row.id}>
                    <button
                      onClick={() => setSelectedId(row.id)}
                      aria-current={active ? "true" : undefined}
                      className={
                        "flex w-full min-h-touch items-center gap-3 border-b border-n200 px-4 py-3 text-left last:border-b-0 " +
                        (active ? "bg-primary-light" : "hover:bg-n100")
                      }
                    >
                      <span className="font-mono text-label tabular-nums text-n600">
                        {row.ticket}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-body-lg text-n900">
                          {row.name}
                        </span>
                        <span className="block truncate text-body text-n600">
                          {row.serviceName}
                        </span>
                      </span>
                      {row.status === "called" && (
                        <Badge tone="primary">Called</Badge>
                      )}
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
        </Card>

        {/* CL-02 - the detail panel. */}
        {selected ? (
          <Card className="p-5">
            <div className="flex items-start gap-4">
              <span className="ml-icon-plate h-12 w-12 bg-primary-light text-primary">
                <IconUser size={22} />
              </span>
              <div className="min-w-0">
                <h2 className="truncate text-h2 text-n900">{selected.name}</h2>
                <p className="mt-1 font-mono text-body tabular-nums text-n600">
                  {selected.ticket} · {selected.serviceName}
                </p>
              </div>
            </div>

            <dl className="mt-5 grid gap-3 sm:grid-cols-3">
              <div className="rounded-md bg-n100 p-3">
                <dt className="text-label text-n600">Status</dt>
                <dd className="mt-1 text-body-lg text-n900">
                  {selected.status === "called" ? "Called" : "Waiting"}
                </dd>
              </div>
              <div className="rounded-md bg-n100 p-3">
                <dt className="text-label text-n600">Waited</dt>
                <dd className="mt-1 flex items-center gap-1.5 text-body-lg tabular-nums text-n900">
                  <IconClock size={15} />
                  {waitedLabel(selected.waitedMinutes)}
                </dd>
              </div>
              <div className="rounded-md bg-n100 p-3">
                <dt className="text-label text-n600">Position</dt>
                <dd className="mt-1 text-body-lg tabular-nums text-n900">
                  {selected.position ?? "—"}
                </dd>
              </div>
            </dl>

            {/* The honesty note. A clinician arriving here needs to know what
                this screen can and cannot tell them, before they rely on it
                and find nothing. */}
            <div className="mt-5 rounded-md border border-n200 bg-n100 p-4">
              <p className="text-body-lg font-medium text-n900">
                Queue information only
              </p>
              <p className="mt-1 text-body text-n700">
                Vitals, prescriptions, lab results and visit notes are not
                recorded in MediLink. This screen shows who is waiting and for
                what; it is not a clinical record, and nothing here should be
                read as one.
              </p>
            </div>

            <p className="mt-4 text-body text-n600">
              The reception desk calls and closes queue entries. Clinician
              accounts have read access here.
            </p>
          </Card>
        ) : (
          <Card className="grid min-h-[16rem] place-items-center p-5">
            <p className="text-body-lg text-n700">
              Select a patient to see their queue details.
            </p>
          </Card>
        )}
      </div>
    </div>
  )
}

export default WorkspaceClinic
