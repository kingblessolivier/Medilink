import { useQuery } from "@tanstack/react-query"
import { api, tokens, type Me } from "../api/client"
import { useQueueActions } from "../hooks/useQueueActions"
import { CheckInForm } from "../components/CheckInForm"
import { QueueTable } from "../components/QueueTable"
import { StatusBar } from "../components/StatusBar"

export function Reception({
  me,
  onSignOut,
}: {
  me: Me
  onSignOut: () => void
}) {
  const actions = useQueueActions()

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
    <div className="min-h-screen">
      <StatusBar
        facilityName={me.facility.name}
        online={actions.online}
        pendingCount={actions.pendingCount}
        syncing={actions.syncing}
        username={me.username}
        onSignOut={() => {
          tokens.clear()
          onSignOut()
        }}
      />

      <main className="mx-auto max-w-5xl px-4 py-4">
        {me.can_manage_queue ? (
          <CheckInForm services={me.services} onCheckIn={actions.checkIn} />
        ) : (
          <p className="card p-4 text-sm text-neutral-600">
            Your role can view the queue but not change it.
          </p>
        )}

        {actions.lastError && (
          <div
            role="alert"
            className="mt-3 flex items-start justify-between gap-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-danger"
          >
            <span>{actions.lastError}</span>
            <button className="shrink-0 underline" onClick={actions.clearError}>
              Dismiss
            </button>
          </div>
        )}

        <div className="mb-3 mt-6 flex items-baseline justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-neutral-500">
            Queue - {totalWaiting} waiting
          </h2>
          {board.data && (
            <span className="text-xs text-neutral-400">
              updated{" "}
              {new Date(board.data.as_of).toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
              })}
            </span>
          )}
        </div>

        {board.isLoading && <p className="text-sm text-neutral-500">Loading...</p>}

        {board.isError && !actions.online && (
          <p className="card p-4 text-sm text-neutral-600">
            Offline. Check-ins are being saved on this device and will sync
            automatically when the connection returns.
          </p>
        )}

        {groups.length === 0 && board.isSuccess && (
          <p className="card p-4 text-sm text-neutral-600">
            Nobody is waiting. Check in the first patient above.
          </p>
        )}

        {groups.map((group) => (
          <QueueTable
            key={group.service}
            group={group}
            canManage={me.can_manage_queue}
            onAction={actions.transition}
          />
        ))}
      </main>
    </div>
  )
}
