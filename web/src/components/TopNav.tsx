import { useState } from "react"
import { Link, NavLink } from "react-router-dom"
import { useI18n } from "../i18n"
import { LanguageToggle } from "./LanguageToggle"
import type { Session } from "../api/types"

/**
 * The top bar, on every surface.
 *
 * One app now serves patients, facility staff and platform admins, so the
 * navbar is the thing that tells you which of those you are. The links change
 * with the session; the bar itself does not, which is what makes signing out
 * of one role and into another feel like the same product rather than three.
 *
 * On patient screens the bottom nav still handles mobile - a thumb reaches the
 * bottom of a phone and not the top. So the patient links here are hidden on
 * small screens; the workspace and platform links are not, because those are
 * desk tools nobody drives one-handed.
 */

type NavItem = { to: string; label: string; end?: boolean }

function itemsFor(session: Session | null, t: (k: string) => string): NavItem[] {
  switch (session?.kind) {
    case "staff":
      return [
        { to: "/workspace", label: t("nav_reception"), end: true },
        { to: "/workspace/appointments", label: t("nav_appointments") },
        { to: "/workspace/doctors", label: t("nav_doctors") },
        { to: "/workspace/services", label: t("nav_services") },
        { to: "/workspace/reports", label: t("nav_reports") },
      ]
    case "admin":
      return [
        { to: "/platform", label: t("nav_overview"), end: true },
        { to: "/platform/verification", label: t("nav_verification") },
        { to: "/platform/triage", label: t("nav_care_guide_monitoring") },
      ]
    default:
      return [
        { to: "/", label: t("nav_home"), end: true },
        { to: "/search", label: t("nav_facilities") },
        { to: "/doctors", label: t("nav_doctors") },
        { to: "/visits", label: t("nav_visits") },
      ]
  }
}

export function TopNav({
  session,
  onSignOut,
}: {
  session: Session | null
  onSignOut: () => void
}) {
  const { t } = useI18n()
  const [open, setOpen] = useState(false)
  const items = itemsFor(session, t)
  const isPatientSurface = !session || session.kind === "patient"

  return (
    <header className="sticky top-0 z-30 border-b border-line bg-surface">
      <div className="mx-auto flex w-full max-w-6xl items-center gap-4 px-4 py-3">
        <Link to={homeFor(session)} className="shrink-0">
          <span className="block text-caption font-semibold uppercase tracking-widest text-primary">
            MediLink
          </span>
          {session?.facility && (
            <span className="block max-w-[14rem] truncate text-small text-ink-muted">
              {session.facility.name}
            </span>
          )}
          {session?.kind === "admin" && (
            <span className="block text-small text-ink-muted">
              {t("nav_platform")}
            </span>
          )}
        </Link>

        {/* Patient links hide on mobile - the bottom nav covers those, and a
            thumb reaches the bottom of a phone, not the top. Staff and admin
            links stay, because those surfaces have no bottom nav. */}
        <nav
          className={
            "min-w-0 flex-1 " + (isPatientSurface ? "hidden md:block" : "hidden sm:block")
          }
        >
          <ul className="flex items-center gap-1 overflow-x-auto">
            {items.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  end={item.end}
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

        <div className="ml-auto flex shrink-0 items-center gap-2">
          <LanguageToggle />

          {session ? (
            <>
              <span className="hidden max-w-[10rem] truncate text-small text-ink-muted sm:block">
                {session.display_name}
              </span>
              <button className="ml-btn-secondary ml-btn-sm" onClick={onSignOut}>
                {t("sign_out")}
              </button>
            </>
          ) : (
            <Link to="/sign-in" className="ml-btn-primary ml-btn-sm">
              {t("sign_in")}
            </Link>
          )}

          {/* Only the staff and admin surfaces need this: their links are the
              only ones that vanish entirely below the `sm` breakpoint. */}
          {!isPatientSurface && (
            <button
              className="ml-btn-secondary ml-btn-sm sm:hidden"
              aria-expanded={open}
              aria-controls="topnav-mobile"
              onClick={() => setOpen((v) => !v)}
            >
              {t("menu")}
            </button>
          )}
        </div>
      </div>

      {!isPatientSurface && open && (
        <nav id="topnav-mobile" className="border-t border-line sm:hidden">
          <ul className="mx-auto max-w-6xl px-2 py-2">
            {items.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  end={item.end}
                  onClick={() => setOpen(false)}
                  className={({ isActive }) =>
                    "block rounded-md px-3 py-2 text-body " +
                    (isActive
                      ? "bg-primary-subtle font-medium text-primary"
                      : "text-ink-muted")
                  }
                >
                  {item.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      )}
    </header>
  )
}

/** Where the logo goes, which is not always `/`. */
export function homeFor(session: Session | null): string {
  if (session?.kind === "staff") return "/workspace"
  if (session?.kind === "admin") return "/platform"
  return "/"
}
