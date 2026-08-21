import type { QueueRow, ServiceGroup } from "../api/client"

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

  return (
    <tr className="border-t border-line">
      <td className="py-2 pr-3 font-mono text-small">{row.ticket_code}</td>
      <td className="py-2 pr-3">{row.display_name}</td>
      <td className="py-2 pr-3 text-small text-ink-muted">{row.phone || "-"}</td>
      <td className="py-2 pr-3 text-small text-ink-muted">
        {new Date(row.joined_at).toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        })}
      </td>
      <td className="py-2 pr-3 text-small text-ink-muted">{row.waited_minutes} min</td>
      <td className="py-2">
        {canManage && (
          <div className="flex justify-end gap-2">
            {!called && (
              <button className="ml-btn-secondary ml-btn-sm" onClick={() => onAction(row.id, "call")}>
                Call
              </button>
            )}
            <button className="ml-btn-primary ml-btn-sm" onClick={() => onAction(row.id, "serve")}>
              Serve
            </button>
            <button className="ml-btn-destructive ml-btn-sm" onClick={() => onAction(row.id, "skip")}>
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
      <h2 className="border-b border-line px-4 py-3 font-semibold">
        {group.service_name_en}
        <span className="ml-2 font-normal text-ink-muted">
          {group.waiting.length} waiting
          {group.called.length > 0 && `, ${group.called.length} called`}
        </span>
      </h2>

      <div className="overflow-x-auto px-4 pb-3">
        <table className="w-full min-w-[36rem] text-left">
          <thead>
            <tr className="text-caption uppercase tracking-wide text-ink-subtle">
              <th className="py-2 pr-3 font-medium">Ticket</th>
              <th className="py-2 pr-3 font-medium">Patient</th>
              <th className="py-2 pr-3 font-medium">Phone</th>
              <th className="py-2 pr-3 font-medium">Arrived</th>
              <th className="py-2 pr-3 font-medium">Waited</th>
              <th />
            </tr>
          </thead>
          <tbody>
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
