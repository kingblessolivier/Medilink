type Props = {
  facilityName: string
  online: boolean
  pendingCount: number
  syncing: boolean
  username: string
  onSignOut: () => void
}

/**
 * Connection state must be unmissable. A receptionist who does not know they
 * are offline will assume patients are being tracked when they are only
 * queued locally.
 */
export function StatusBar({
  facilityName,
  online,
  pendingCount,
  syncing,
  username,
  onSignOut,
}: Props) {
  const label = syncing
    ? "Syncing..."
    : online
      ? pendingCount > 0
        ? `Online - ${pendingCount} pending`
        : "Online"
      : `Offline - ${pendingCount} pending`

  const tone = !online
    ? "bg-warning text-white"
    : pendingCount > 0 || syncing
      ? "bg-amber-100 text-warning"
      : "bg-green-100 text-success"

  return (
    <header className="flex flex-wrap items-center justify-between gap-3 border-b border-neutral-200 bg-white px-4 py-3">
      <div>
        <h1 className="text-lg font-semibold leading-tight">{facilityName}</h1>
        <p className="text-sm text-neutral-500">
          {new Date().toLocaleDateString(undefined, {
            weekday: "short",
            day: "numeric",
            month: "short",
          })}
        </p>
      </div>

      <div className="flex items-center gap-3">
        <span
          role="status"
          className={"rounded-full px-3 py-1 text-sm font-medium " + tone}
        >
          {label}
        </span>
        <span className="text-sm text-neutral-500">{username}</span>
        <button className="btn-secondary" onClick={onSignOut}>
          Sign out
        </button>
      </div>
    </header>
  )
}
