import { NavLink } from "react-router-dom"
import type { ReactNode } from "react"
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

        {/* Below `lg` the sections flatten into one scrolling row. A phone
            has no room for a sidebar, and a receptionist on a tablet should
            not lose half the width to navigation. */}
        <nav className="px-2 py-2 lg:px-3 lg:py-2">
          <div className="flex gap-1 overflow-x-auto lg:block lg:space-y-5 lg:overflow-visible">
            {sections.map((section) => (
              <div key={section.label} className="contents lg:block">
                {/* The group label is desktop-only: in the flattened row it
                    would be an unclickable item sitting in a list of
                    clickable ones. */}
                <p className="ml-label hidden px-2 pb-1.5 lg:block">
                  {section.label}
                </p>

                {section.items.map(({ to, label, icon, end }) => (
                  <NavLink
                    key={to}
                    to={to}
                    end={end}
                    className={({ isActive }) =>
                      "group flex min-h-touch items-center gap-2.5 whitespace-nowrap rounded-md px-2.5 text-body-lg transition-colors lg:min-h-0 lg:py-2 " +
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
