import { NavLink } from "react-router-dom"
import { useI18n } from "../i18n"

const TABS = [
  { to: "/", key: "nav_home" },
  { to: "/search", key: "nav_facilities" },
  { to: "/visits", key: "nav_visits" },
  { to: "/profile", key: "nav_profile" },
] as const

export function BottomNav() {
  const { t } = useI18n()

  return (
    <nav className="fixed inset-x-0 bottom-0 border-t border-neutral-200 bg-white">
      <ul className="mx-auto flex max-w-md">
        {TABS.map((tab) => (
          <li key={tab.to} className="flex-1">
            <NavLink
              to={tab.to}
              end={tab.to === "/"}
              className={({ isActive }) =>
                "flex min-h-touch items-center justify-center py-2 text-sm " +
                (isActive ? "font-semibold text-primary" : "text-neutral-500")
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
