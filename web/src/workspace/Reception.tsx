import { useQuery } from "@tanstack/react-query"
import { api } from "../api/client"
import type { useQueueActions } from "./useQueueActions"
import { CheckInForm } from "./CheckInForm"
import { QueueTable } from "./QueueTable"
import { EmptyState, Notice } from "../ui"

/**
 * The reception desk.
 *
 * The measured constraint from docs/11 section 7: a check-in stays under ten
 * seconds and never needs the mouse. Nothing on this screen may come between
 * the receptionist and that form - which is why the form is at the top, why it
 * keeps focus after a submit, and why the queue below it never steals it.
 *
 * `actions` is passed in rather than hooked here so the offline queue survives
 * navigation to the other workspace screens. See App.tsx.
 */
export function Reception({
  actions,
}: {
  actions: ReturnType<typeof useQueueActions>
}) {
  // The session says WHICH facility; /staff/me says what that facility
  // offers. The check-in form needs the service list, and putting it on the
  // session would load it for every admin and patient who never open this.
  const me = useQuery({
    queryKey: ["staff-me"],
    queryFn: api.staffMe,
    staleTime: 10 * 60_000,
  }).data

  const board = useQuery({
    queryKey: ["board"],
    queryFn: api.board,
    // The board changes as staff act on it, not on its own. 15 s is well
    // inside the responsiveness a reception desk needs and costs nothing.
    refetchInterval: 15_000,
    // Keep showing the last board while offline rather than blanking it.
    refetchOnWindowFocus: true,
    retry: 1,
  })

  const groups = board.data?.services ?? []
  const totalWaiting = groups.reduce((n, g) => n + g.waiting.length, 0)

  return (
    <div className="mx-auto w-full max-w-5xl">
      {(me?.can_manage_queue ?? false) ? (
        <CheckInForm services={me?.services ?? []} onCheckIn={actions.checkIn} />
      ) : (
        <Notice tone="info">
          Your role can view the queue but not change it.
        </Notice>
      )}

      {actions.lastError && (
        <div
          role="alert"
          className="mt-3 flex items-start justify-between gap-3 rounded-lg border border-danger-border bg-danger-subtle p-3 text-small text-danger"
        >
          <span>{actions.lastError}</span>
          <button className="shrink-0 underline" onClick={actions.clearError}>
            Dismiss
          </button>
        </div>
      )}

      <div className="mb-3 mt-6 flex items-baseline justify-between">
        <h2 className="ml-label">
          Queue - {totalWaiting} waiting
        </h2>
        {board.data && (
          <span className="text-caption tabular-nums text-ink-subtle">
            updated{" "}
            {new Date(board.data.as_of).toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
            })}
          </span>
        )}
      </div>

      {board.isLoading && (
        <p className="text-small text-ink-muted">Loading...</p>
      )}

      {board.isError && !actions.online && (
        <Notice tone="warning">
          Offline. Check-ins are being saved on this device and will sync
          automatically when the connection returns.
        </Notice>
      )}

      {groups.length === 0 && board.isSuccess && (
        <EmptyState
          title="Nobody is waiting."
          body="Check in the first patient above."
        />
      )}

      {groups.map((group) => (
        <QueueTable
          key={group.service}
          group={group}
          canManage={(me?.can_manage_queue ?? false)}
          onAction={actions.transition}
        />
      ))}
    </div>
  )
}
