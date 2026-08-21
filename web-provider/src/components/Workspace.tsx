import { NavLink } from "react-router-dom"
import type { ReactNode } from "react"
import type { Me } from "../api/client"
import { Chip } from "../ui"

/**
 * The provider workspace shell.
 *
 * Deliberately unlike the patient surface: a sidebar, denser type, tables
 * rather than cards. This is a tool somebody uses for eight hours, not a page
 * they visit when unwell, and making the two look alike would help nobody.
 *
 * The connection indicator lives in the header on every screen, not just
 * reception. A receptionist who does not know they are offline will assume
 * patients are being tracked when they are only queued locally.
 */

const NAV = [
  { to: "/", label: "Reception", end: true },
  { to: "/appointments", label: "Appointments" },
  { to: "/doctors", label: "Doctors" },
  { to: "/services", label: "Services" },
  { to: "/reports", label: "Reports" },
] as const

type Props = {
  me: Me
  online: boolean
  pendingCount: number
  syncing: boolean
  onSignOut: () => void
  children: ReactNode
}

export function Workspace({
  me,
  online,
  pendingCount,
  syncing,
  onSignOut,
  children,
}: Props) {
  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[15rem_minmax(0,1fr)]">
      {/* ------------------------------------------------------- sidebar */}
      <aside className="border-b border-line bg-surface lg:sticky lg:top-0 lg:h-screen lg:border-b-0 lg:border-r">
        <div className="px-4 py-4">
          <p className="text-caption font-semibold uppercase tracking-widest text-primary">
            MediLink
          </p>
          <p className="mt-0.5 truncate text-body font-semibold">
            {me.facility.name}
          </p>
          <p className="text-small text-ink-muted">{me.facility.district}</p>
        </div>

        <nav className="px-2 pb-3">
          <ul className="flex gap-1 overflow-x-auto lg:block lg:space-y-0.5 lg:overflow-visible">
            {NAV.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  end={"end" in item ? item.end : undefined}
                  className={({ isActive }) =>
                    "block whitespace-nowrap rounded-md px-3 py-2 text-body transition-colors " +
                    (isActive
                      ? "bg-primary-subtle font-medium text-primary"
                      : "text-ink-muted hover:bg-surface-sunken hover:text-ink")
                  }
                >
                  {item.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      </aside>

      {/* -------------------------------------------------------- content */}
      <div className="flex min-h-screen flex-col">
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-line bg-surface px-4 py-3">
          <p className="text-small text-ink-muted">
            {new Date().toLocaleDateString(undefined, {
              weekday: "long",
              day: "numeric",
              month: "long",
            })}
          </p>

          <div className="flex items-center gap-3">
            <ConnectionState
              online={online}
              pendingCount={pendingCount}
              syncing={syncing}
            />
            <span className="text-small text-ink-muted">{me.username}</span>
            <button className="ml-btn-secondary ml-btn-sm" onClick={onSignOut}>
              Sign out
            </button>
          </div>
        </header>

        <main className="flex-1 p-4">{children}</main>
      </div>
    </div>
  )
}

function ConnectionState({
  online,
  pendingCount,
  syncing,
}: {
  online: boolean
  pendingCount: number
  syncing: boolean
}) {
  if (syncing) return <Chip tone="warning">Syncing...</Chip>
  if (!online) {
    return (
      <Chip tone="warning">
        Offline{pendingCount > 0 ? ` - ${pendingCount} pending` : ""}
      </Chip>
    )
  }
  if (pendingCount > 0) return <Chip tone="warning">{pendingCount} pending</Chip>
  return <Chip tone="success">Online</Chip>
}
