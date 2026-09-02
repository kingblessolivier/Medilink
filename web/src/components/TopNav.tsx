import { useEffect, useRef } from "react"
import { Link, NavLink, useLocation } from "react-router-dom"
import { useI18n } from "../i18n"
import { useTriageStatus } from "../hooks/useTriageStatus"
import { LanguageToggle } from "./LanguageToggle"
import {
  IconCalendar,
  IconHeart,
  IconHospital,
  IconSearch,
  IconShield,
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

/** Surfaces that carry their own sidebar navigation. */
const DASHBOARD_PREFIXES = ["/workspace", "/platform"]

function onDashboard(pathname: string): boolean {
  return DASHBOARD_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(prefix + "/"),
  )
}

/**
 * Which links the bar carries, decided by WHERE you are - not by who you are.
 *
 * It used to switch on `session.kind` alone: staff and admin got an empty
 * array, because their sections live in the DashboardShell sidebar and
 * repeating them here was duplication. That is right on `/workspace` and
 * `/platform`, and wrong everywhere else - the sidebar only renders on those
 * two surfaces. A signed-in admin who opened the patient home got the patient
 * page with no sidebar AND no top-bar links: no navigation at all, on a route
 * their role is allowed to visit, with only the wordmark to escape by.
 *
 * Staff and admin genuinely need the patient app - checking what a patient
 * sees is part of running this - so the fix is to keep the links and drop them
 * only on the surfaces that already have a sidebar.
 */
function itemsFor(
  session: Session | null,
  pathname: string,
  t: (k: string) => string,
  careGuideAvailable: boolean,
): NavItem[] {
  switch (session?.kind) {
    case "staff":
    case "admin":
      return onDashboard(pathname) ? [] : patientItems(t, careGuideAvailable)
    default:
      return patientItems(t, careGuideAvailable)
  }
}

/**
 * The third link mirrors the bottom bar: the Care Guide takes it when the
 * clinician gate is open, Doctors holds it when it is shut. See BottomNav for
 * why, and note that the two lists have to agree - a link that exists on a
 * phone and not on a desktop is how a feature quietly becomes unreachable.
 */
function patientItems(
  t: (k: string) => string,
  careGuideAvailable: boolean,
): NavItem[] {
  return [
    { to: "/", label: t("nav_home"), icon: IconHospital, end: true },
    { to: "/search", label: t("nav_facilities"), icon: IconSearch },
    careGuideAvailable
      ? { to: "/care-guide", label: t("care_guide"), icon: IconHeart }
      : { to: "/doctors", label: t("nav_doctors"), icon: IconStethoscope },
    { to: "/insurance", label: t("nav_insurance"), icon: IconShield },
    { to: "/visits", label: t("nav_visits"), icon: IconCalendar },
  ]
}

export function TopNav({
  session,
  onSignOut,
}: {
  session: Session | null
  onSignOut: () => void
}) {
  const { t } = useI18n()
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
  const { pathname } = useLocation()
  const { available: careGuideAvailable } = useTriageStatus()
  const items = itemsFor(session, pathname, t, careGuideAvailable)

  return (
    <header ref={barRef} className="sticky top-0 z-30 border-b border-n200 bg-white/95 backdrop-blur supports-[backdrop-filter]:bg-white/80">
      <div className="ml-shell flex items-center gap-4 py-3">
        {/* The home link was 68x16 - the wordmark's own text box. It is on
            every screen and it is how you get back, so it gets a real target
            rather than the height of a caption. */}
        <Link
          to={homeFor(session)}
          className="flex min-h-touch shrink-0 flex-col justify-center rounded-md px-1 -mx-1 hover:bg-n100"
        >
          <span className="block text-label uppercase tracking-widest text-primary">
            MediLink
          </span>
          {session?.facility && (
            <span className="block max-w-[14rem] truncate text-body text-n700">
              {session.facility.name}
            </span>
          )}
          {session?.kind === "admin" && (
            <span className="block text-body text-n700">
              {t("nav_platform")}
            </span>
          )}
        </Link>

        {/* Patient links only. They hide on mobile because the bottom tab bar
            covers them, and a thumb reaches the bottom of a phone rather than
            the top.

            Staff and admin carry no links here at all - their sections live in
            the DashboardShell sidebar. Until this was fixed, a hamburger button
            still rendered on those surfaces and opened an empty panel, because
            the items were moved to the sidebar and the control that revealed
            them was left behind. It was also what pushed the bar past the edge
            of a 360px phone. */}
{items.length > 0 && (
        <nav className="hidden min-w-0 flex-1 md:block">
          <ul className="flex items-center gap-1 overflow-x-auto">
            {items.map(({ to, label, icon: Glyph, end }) => (
              <li key={to}>
                <NavLink
                  to={to}
                  end={end}
                  // Active state is weight, colour and a 2px underline - not
                  // a filled plate. A tinted box on every active item put a
                  // second competing "button" in a bar that already has a
                  // primary action in it, and read as heavier than the Sign
                  // in button it sat beside. The underline is the quieter
                  // convention and leaves the bar visually light.
                  className={({ isActive }) =>
                    "relative flex items-center gap-2 whitespace-nowrap rounded-md px-3 py-2 text-body-lg transition-colors " +
                    "after:absolute after:inset-x-3 after:-bottom-px after:h-0.5 after:rounded-full after:transition-colors " +
                    (isActive
                      ? "font-medium text-n900 after:bg-primary"
                      : "text-n700 after:bg-transparent hover:text-n900")
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
        )}

        <div className="ml-auto flex shrink-0 items-center gap-2">
          <LanguageToggle />

          {session ? (
            <>
              <span className="hidden max-w-[10rem] items-center gap-1.5 truncate text-body text-n700 sm:flex">
                <IconUser size={15} className="shrink-0 text-n600" />
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

        </div>
      </div>

    </header>
  )
}

/** Where the logo goes, which is not always `/`. */
export function homeFor(session: Session | null): string {
  if (session?.kind === "staff") return "/workspace"
  if (session?.kind === "admin") return "/platform"
  return "/"
}
