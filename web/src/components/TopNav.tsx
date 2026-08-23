import { useEffect, useRef, useState } from "react"
import { Link, NavLink } from "react-router-dom"
import { useI18n } from "../i18n"
import { LanguageToggle } from "./LanguageToggle"
import {
  IconCalendar,
  IconChevronRight,
  IconHospital,
  IconSearch,
  IconStethoscope,
  IconUser,
} from "../ui/icons"
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

type Glyph = typeof IconHospital
type NavItem = { to: string; label: string; icon: Glyph; end?: boolean }

function itemsFor(session: Session | null, t: (k: string) => string): NavItem[] {
  switch (session?.kind) {
    // Staff and admin sections live in the DashboardShell sidebar, which is
    // where they can grow. Repeating them here was duplication, and it is
    // what forced a hamburger menu onto the dashboards.
    case "staff":
    case "admin":
      return []
    default:
      return [
        { to: "/", label: t("nav_home"), icon: IconHospital, end: true },
        { to: "/search", label: t("nav_facilities"), icon: IconSearch },
        { to: "/doctors", label: t("nav_doctors"), icon: IconStethoscope },
        { to: "/visits", label: t("nav_visits"), icon: IconCalendar },
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
  const barRef = useRef<HTMLElement>(null)

  // The dashboard sidebar sticks directly beneath this bar, and the bar is
  // not a fixed height: the controls inside it are 44px on a phone and 36px
  // from `sm` up, so it is 69px on one and 61px on the other. A hard-coded
  // offset is wrong at one breakpoint - it was overlapping by a pixel, which
  // slid a hairline of content under the border.
  //
  // Published as a CSS variable so the sidebar can just use it, and remeasured
  // on resize because crossing the breakpoint changes it.
  useEffect(() => {
    const bar = barRef.current
    if (!bar || typeof ResizeObserver === "undefined") return
    const publish = () =>
      document.documentElement.style.setProperty(
        "--topnav-h",
        `${bar.getBoundingClientRect().height}px`,
      )
    publish()
    const observer = new ResizeObserver(publish)
    observer.observe(bar)
    return () => observer.disconnect()
  }, [])
  const items = itemsFor(session, t)
  const isPatientSurface = !session || session.kind === "patient"

  return (
    <header ref={barRef} className="sticky top-0 z-30 border-b border-line bg-surface/95 backdrop-blur supports-[backdrop-filter]:bg-surface/80">
      <div className="ml-shell flex items-center gap-4 py-3">
        {/* The home link was 68x16 - the wordmark's own text box. It is on
            every screen and it is how you get back, so it gets a real target
            rather than the height of a caption. */}
        <Link
          to={homeFor(session)}
          className="flex min-h-touch shrink-0 flex-col justify-center rounded-md px-1 -mx-1 hover:bg-surface-sunken"
        >
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
            {items.map(({ to, label, icon: Glyph, end }) => (
              <li key={to}>
                <NavLink
                  to={to}
                  end={end}
                  className={({ isActive }) =>
                    "flex items-center gap-2 whitespace-nowrap rounded-md px-3 py-2 text-body transition-colors " +
                    (isActive
                      ? "bg-primary-subtle font-medium text-primary"
                      : "text-ink-muted hover:bg-surface-sunken hover:text-ink")
                  }
                >
                  {/* Same glyphs as the bottom tab bar, so moving between a
                      phone and a desktop feels like one product. */}
                  <Glyph size={17} />
                  {label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>

        <div className="ml-auto flex shrink-0 items-center gap-2">
          <LanguageToggle />

          {session ? (
            <>
              <span className="hidden max-w-[10rem] items-center gap-1.5 truncate text-small text-ink-muted sm:flex">
                <IconUser size={15} className="shrink-0 text-ink-subtle" />
                <span className="truncate">{session.display_name}</span>
              </span>
              <button
                className="ml-btn-secondary ml-btn-sm min-h-touch sm:min-h-0 sm:h-9"
                onClick={onSignOut}
              >
                {t("sign_out")}
              </button>
            </>
          ) : (
            <Link to="/sign-in" className="ml-btn-primary ml-btn-sm min-h-touch sm:min-h-0 sm:h-9">
              {t("sign_in")}
            </Link>
          )}

          {/* Only the staff and admin surfaces need this: their links are the
              only ones that vanish entirely below the `sm` breakpoint. */}
          {!isPatientSurface && (
            <button
              className="ml-btn-secondary ml-btn-sm sm:hidden min-h-touch sm:min-h-0 sm:h-9"
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
          <ul className="ml-shell py-2">
            {items.map(({ to, label, icon: Glyph, end }) => (
              <li key={to}>
                <NavLink
                  to={to}
                  end={end}
                  onClick={() => setOpen(false)}
                  className={({ isActive }) =>
                    "flex min-h-touch items-center gap-3 rounded-md px-3 text-body " +
                    (isActive
                      ? "bg-primary-subtle font-medium text-primary"
                      : "text-ink-muted")
                  }
                >
                  <Glyph size={18} />
                  <span className="flex-1">{label}</span>
                  <IconChevronRight size={16} className="text-ink-subtle" />
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
