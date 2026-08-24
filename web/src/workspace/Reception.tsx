import { useQuery } from "@tanstack/react-query"
import { api } from "../api/client"
import type { useQueueActions } from "./useQueueActions"
import { CheckInForm } from "./CheckInForm"
import { QueueTable } from "./QueueTable"
import { EmptyState, Notice } from "../ui"
import { IconClock, IconUsers } from "../ui/icons"

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
  const meQuery = useQuery({
    queryKey: ["staff-me"],
    queryFn: api.staffMe,
    staleTime: 10 * 60_000,
  })
  const me = meQuery.data

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
    <div className="mx-auto w-full max-w-6xl">
      {/* The screen had no h1 at all - the only page in the product without
          one. A screen-reader user landed here with nothing to orient on, and
          it broke the heading order every other screen follows. */}
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-h2">Reception</h1>
          <p className="mt-1 text-small text-ink-muted">
            {me?.facility?.name ?? ""}
          </p>
        </div>
        <p className="text-small tabular-nums text-ink-muted">
          {new Date().toLocaleDateString(undefined, {
            weekday: "long",
            day: "numeric",
            month: "long",
          })}
        </p>
      </div>

      {/* Three states, not two. `me?.can_manage_queue ?? false` collapsed
          "still loading" into "not allowed", so for the first moment of every
          visit a facility administrator was told their role could not change
          the queue - a definite claim about someone's permissions, made
          before we knew any of them. Say nothing until we do. */}
      {meQuery.isLoading ? (
        <div className="ml-card h-[7.5rem] animate-pulse bg-surface-sunken" />
      ) : me?.can_manage_queue ? (
        <CheckInForm services={me.services ?? []} onCheckIn={actions.checkIn} />
      ) : (
        <Notice tone="info">
          Your role can view the queue but not change it.
        </Notice>
      )}

      {/* Check-in is the one operation that may never fail, so it must also
          never be silent. A receptionist working through an outage types a
          name, the form clears, and the person does NOT appear on the board -
          the board comes from the server. Without this line the only honest
          reading is "it did not work", and they check the same patient in
          again.

          Driven by `pendingCount`, not by whether the board request failed.
          React Query serves the cached board while offline, so `board.isError`
          stays false and the old notice below never appeared at exactly the
          moment it was needed. */}
      {actions.pendingCount > 0 && (
        <div
          role="status"
          className="mt-3 flex items-center gap-2.5 rounded-lg border border-warning-border bg-warning-subtle p-3 text-small text-warning"
        >
          <IconClock size={16} className="shrink-0" />
          <span>
            <span className="tabular-nums font-medium">
              {actions.pendingCount}
            </span>{" "}
            {actions.pendingCount === 1 ? "check-in is" : "check-ins are"} saved
            on this device.{" "}
            {actions.syncing
              ? "Sending them now."
              : actions.online
                ? "Sending shortly."
                : "They will send when the connection returns."}
          </span>
        </div>
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

      <div className="mb-3 mt-8 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-h3">
          Queue
          <span className="ml-2 font-normal text-ink-muted">
            <span className="tabular-nums">{totalWaiting}</span> waiting
          </span>
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

      {!actions.online && (
        <Notice tone="warning">
          Offline. You are looking at the last board this device received;
          check-ins are saved here and sync when the connection returns.
        </Notice>
      )}

      {groups.length === 0 && board.isSuccess && (
        <EmptyState icon={<IconUsers size={20} />}
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
