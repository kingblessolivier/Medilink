import { NavLink, useLocation } from "react-router-dom"
import { useEffect, useState, type ReactNode } from "react"
import { useI18n } from "../i18n"
import { IconChevronRight } from "../ui/icons"

/**
 * The shell for the two dashboard surfaces: the facility workspace and the
 * platform portal.
 *
 * Top nav plus side nav, and they carry different things on purpose:
 *
 *   TOP   who you are, which facility, language, sign out. Constant.
 *   SIDE  where you can go. Grows as a surface grows.
 *
 * They used to be one horizontal strip, which was fine at five links and
 * stopped being fine at nine - the platform portal now has nine sections and
 * they would have wrapped or scrolled sideways. A dashboard's navigation
 * should be able to grow without the layout arguing about it.
 *
 * The patient app keeps the top bar alone. It has five destinations and a
 * bottom tab bar on a phone; a sidebar there would be a filing cabinet
 * bolted to a doorway.
 *
 * Sections, not a flat list. Nine links in one column is a menu somebody has
 * to read; three groups of three is a map.
 */

export type NavSection = {
  label: string
  items: { to: string; label: string; icon: ReactNode; end?: boolean }[]
}

export function DashboardShell({
  title,
  subtitle,
  sections,
  children,
}: {
  /** What this surface IS - "Workspace", "Platform". Not the page title. */
  title: string
  subtitle?: string
  sections: NavSection[]
  children: ReactNode
}) {
  const { t } = useI18n()
  const [expanded, setExpanded] = useState(false)
  const location = useLocation()
  useEffect(() => setExpanded(false), [location.pathname])
  const current = sections.flatMap(section => section.items).find(item => item.to === location.pathname)?.label ?? title

  return (
    <div className="lg:grid lg:grid-cols-[16rem_minmax(0,1fr)]">
      {/* ---------------------------------------------------------- side */}
      <aside
        aria-label={t("nav_sections")}
        className="border-b border-n200 bg-white lg:sticky lg:top-[var(--topnav-h,4.25rem)] lg:h-[calc(100vh-var(--topnav-h,4.25rem))] lg:overflow-y-auto lg:border-b-0 lg:border-r"
      >
        <div className="hidden px-5 pb-2 pt-5 lg:block">
          <p className="text-h3">{title}</p>
          {subtitle && (
            <p className="mt-0.5 truncate text-body text-n700">
              {subtitle}
            </p>
          )}
        </div>

        <button type="button" aria-expanded={expanded} aria-controls="dashboard-sections" onClick={() => setExpanded(value => !value)} className="flex min-h-touch w-full items-center justify-between gap-3 px-4 text-left font-medium text-primary lg:hidden">
          <span className="min-w-0 break-words">{current}</span>
          <IconChevronRight size={20} className={expanded ? "rotate-90 shrink-0" : "shrink-0"} />
        </button>
        <nav id="dashboard-sections" className={(expanded ? "block " : "hidden ") + "px-2 py-2 lg:block lg:px-3 lg:py-2"}>
          <div className="space-y-5">
            {sections.map((section) => (
              <div key={section.label}>
                {/* The group label is desktop-only: in the flattened row it
                    would be an unclickable item sitting in a list of
                    clickable ones. */}
                <p className="ml-label px-2 pb-1.5">
                  {section.label}
                </p>

                {section.items.map(({ to, label, icon, end }) => (
                  <NavLink
                    key={to}
                    to={to}
                    end={end}
                    className={({ isActive }) =>
                      "group flex min-h-touch items-center gap-2.5 whitespace-nowrap rounded-md px-2.5 text-body-lg transition-colors lg:py-2 " +
                      (isActive
                        ? "bg-primary-light font-medium text-primary"
                        : "text-n700 hover:bg-n100 hover:text-n900")
                    }
                  >
                    <span className="shrink-0">{icon}</span>
                    <span className="flex-1 truncate">{label}</span>
                    {/* Desktop only, and only on the active row: a chevron on
                        every item is decoration, on the current one it marks
                        where you are without relying on the tint. */}
                    <IconChevronRight
                      size={15}
                      className="hidden shrink-0 opacity-0 group-aria-[current=page]:opacity-100 lg:block"
                    />
                  </NavLink>
                ))}
              </div>
            ))}
          </div>
        </nav>
      </aside>

      {/* ------------------------------------------------------- content */}
      <main className="min-w-0 px-4 py-6 sm:px-6 lg:px-8">{children}</main>
    </div>
  )
}
