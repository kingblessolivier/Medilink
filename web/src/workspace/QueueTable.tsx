import type { QueueRow, ServiceGroup } from "../api/client"
import { Chip } from "../ui"
import { IconChevronRight, IconClock, IconUser } from "../ui/icons"

/**
 * One service's queue.
 *
 * The action hierarchy is the point, and it used to be wrong. Every row
 * carried a filled primary "Serve" button, so an eighteen-person queue put
 * eighteen of the loudest control on the screen and the receptionist's actual
 * next action - calling whoever is next - was the quiet one beside it.
 *
 * It works the other way round now:
 *
 *   waiting  ->  Call is primary. It is the only thing you do to somebody who
 *                is waiting, and usually only to the person at the top.
 *   called   ->  Serve is primary, because that patient is with a clinician
 *                and finishing them is what comes next.
 *
 * The called row is also visually lifted out of the list. Somebody has been
 * called and is walking to a door; a receptionist glancing at the screen needs
 * to see who that is without reading a status column.
 */

type Props = {
  group: ServiceGroup
  canManage: boolean
  onAction: (id: number, action: "call" | "serve" | "skip" | "cancel") => void
}

function Row({
  row,
  canManage,
  onAction,
}: {
  row: QueueRow
  canManage: boolean
  onAction: Props["onAction"]
}) {
  const called = row.status === "called"

  // Anything past a working day is a queue nobody closed - almost always
  // yesterday's list still open this morning. Flagged rather than hidden: it
  // is the receptionist's to clear, and silently dropping people would be
  // worse than showing a number that looks wrong.
  const stale = row.waited_minutes > 8 * 60

  return (
    <tr
      className={
        "border-t border-n200 " +
        (called ? "bg-primary-light/50" : "hover:bg-n100/50")
      }
    >
      <td className="py-2.5 pr-3">
        <span className="flex items-center gap-2">
          {/* A marker on the row, not a word in a column. The called patient
              is the one fact this table has to convey at a glance. */}
          <span
            aria-hidden="true"
            className={
              "h-1.5 w-1.5 shrink-0 rounded-full " +
              (called ? "bg-primary" : "bg-transparent")
            }
          />
          <span className="font-mono text-body tabular-nums">
            {row.ticket_code}
          </span>
        </span>
      </td>

      <td className="py-2.5 pr-3">
        <span className="block truncate">{row.display_name}</span>
        {called && (
          <span className="mt-0.5 block text-label text-primary">
            With a clinician
          </span>
        )}
      </td>

      <td className="py-2.5 pr-3 text-body tabular-nums text-n700">
        {row.phone || "—"}
      </td>

      <td className="py-2.5 pr-3 text-body tabular-nums text-n700">
        {new Date(row.joined_at).toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        })}
      </td>

      <td className="py-2.5 pr-3 text-body tabular-nums">
        {stale ? (
          <Chip tone="warning">
            <IconClock size={13} />
            {formatWaited(row.waited_minutes)}
          </Chip>
        ) : (
          <span className="text-n700">
            {formatWaited(row.waited_minutes)}
          </span>
        )}
      </td>

      <td className="py-2.5">
        {canManage && (
          <div className="flex justify-end gap-1.5">
            {called ? (
              <button
                className="ml-btn-primary ml-btn-sm"
                onClick={() => onAction(row.id, "serve")}
              >
                Served
              </button>
            ) : (
              <button
                className="ml-btn-primary ml-btn-sm"
                onClick={() => onAction(row.id, "call")}
              >
                Call
                <IconChevronRight size={14} />
              </button>
            )}

            {/* Secondary, and only where it makes sense: serving somebody who
                was never called is a correction, not the normal path. */}
            {!called && (
              <button
                className="ml-btn-secondary ml-btn-sm"
                onClick={() => onAction(row.id, "serve")}
              >
                Served
              </button>
            )}

            <button
              className="ml-btn-ghost ml-btn-sm text-n700 hover:text-danger"
              onClick={() => onAction(row.id, "skip")}
            >
              {called ? "No show" : "Left"}
            </button>
          </div>
        )}
      </td>
    </tr>
  )
}

export function QueueTable({ group, canManage, onAction }: Props) {
  const total = group.waiting.length + group.called.length
  if (total === 0) return null

  return (
    <section className="ml-card mb-4 overflow-hidden">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-n200 px-4 py-3">
        <h3 className="text-h3">{group.service_name_en}</h3>
        <span className="flex items-center gap-1.5 text-body text-n700">
          <IconUser size={14} className="text-n600" />
          <span className="tabular-nums">{group.waiting.length}</span> waiting
        </span>
        {group.called.length > 0 && (
          <Chip tone="success">
            {group.called.length} with a clinician
          </Chip>
        )}
      </div>

      <div className="ml-scroll-x px-4 pb-3">
        <table className="w-full min-w-[38rem] text-left">
          <thead>
            <tr className="text-label uppercase tracking-wide text-n600">
              <th className="py-2 pr-3 font-medium">Ticket</th>
              <th className="py-2 pr-3 font-medium">Patient</th>
              <th className="py-2 pr-3 font-medium">Phone</th>
              <th className="py-2 pr-3 font-medium">Arrived</th>
              <th className="py-2 pr-3 font-medium">Waited</th>
              <th>
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {/* Called first, always. They are the ones something is happening
                to, and they should not be hunted for in a list of eighteen. */}
            {group.called.map((row) => (
              <Row key={row.id} row={row} canManage={canManage} onAction={onAction} />
            ))}
            {group.waiting.map((row) => (
              <Row key={row.id} row={row} canManage={canManage} onAction={onAction} />
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

/**
 * "3405 min" is a number nobody can read at a glance. Past an hour this reads
 * as hours and minutes, which is how a receptionist actually thinks about a
 * wait.
 */
function formatWaited(minutes: number): string {
  if (minutes < 60) return `${minutes} min`
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  if (hours < 24) return rest ? `${hours}h ${rest}m` : `${hours}h`
  return `${Math.floor(hours / 24)}d ${hours % 24}h`
}
