import { NavLink } from "react-router-dom"
import { useI18n } from "../i18n"

// Five items maximum. Anything beyond that stops being navigation and
// starts being a menu somebody has to read.
const TABS = [
  { to: "/", key: "nav_home" },
  { to: "/search", key: "nav_facilities" },
  { to: "/doctors", key: "nav_doctors" },
  { to: "/visits", key: "nav_visits" },
  { to: "/profile", key: "nav_profile" },
] as const

export function BottomNav() {
  const { t } = useI18n()

  return (
    /* Hidden from `md` up. A thumb reaches the bottom of a phone; on a
       desktop it is a bar pinned to the bottom of a 1440px window with the
       same links already in the top bar, which is duplication and clutter. */
    <nav className="fixed inset-x-0 bottom-0 z-20 border-t border-line bg-surface md:hidden">
      <ul className="mx-auto flex max-w-2xl">
        {TABS.map((tab) => (
          <li key={tab.to} className="flex-1">
            <NavLink
              to={tab.to}
              end={tab.to === "/"}
              className={({ isActive }) =>
                "flex min-h-touch items-center justify-center py-2 text-small " +
                (isActive ? "font-semibold text-primary" : "text-ink-muted")
              }
            >
              {t(tab.key)}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  )
}
