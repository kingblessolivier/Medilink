import { NavLink } from "react-router-dom"
import { useI18n } from "../i18n"
import {
  IconCalendar,
  IconHeart,
  IconHospital,
  IconSearch,
  IconUser,
} from "../ui/icons"

/**
 * The primary navigation on a phone, which is how most people reach MediLink.
 *
 * It used to be five text labels crammed into a 45px strip. In Kinyarwanda
 * those labels are long - "Umwirondoro", "Amavuriro" - so at 360px each tab
 * got about 72px and the text shrank to the point of being scanned rather
 * than read. Icons carry the meaning; the label confirms it.
 *
 * The tab labels are their OWN keys, not the nav ones. A tab needs a word
 * that fits in 72px; the top bar has room for the fuller phrase. Sharing them
 * meant "Umwirondoro" clipping against the edge of the screen.
 *
 * Sizing, deliberately:
 *
 * - The tap target is the whole tab, 56px tall plus the safe area, not just
 *   the glyph. A miss on a bottom bar is the most annoying miss on a phone.
 * - `pb-[env(safe-area-inset-bottom)]` keeps the row clear of the home
 *   indicator on a gesture-navigation phone, where the bottom 20-30px are
 *   swallowed by the system.
 * - Labels are `caption` and allowed to truncate rather than wrap. A tab that
 *   grows to two lines shifts the whole bar and misaligns every icon.
 *
 * Five items maximum. Beyond that it stops being navigation and becomes a
 * menu somebody has to read.
 */
/**
 * The third tab is the Care Guide, unconditionally.
 *
 * Browsing every doctor in Kigali is a weak thing for a patient to do: a
 * doctor is only reachable through the facility they practise at, and someone
 * who feels unwell does not know which doctor they need. Symptom-first
 * routing answers the question they actually have, so it gets the tab.
 *
 * This deliberately does NOT consult `/triage/status`. While the clinician
 * gate is shut the tab lands on the Care Guide's unavailable screen, which
 * says plainly that it is awaiting sign-off and offers facility search and
 * the doctor list as the ways on. That was a product decision taken with the
 * trade-off understood: the tab reflects where the product is going, and the
 * landing screen is honest about where it is today.
 *
 * The gate itself is untouched and still absolute - `/triage/status` governs
 * whether the flow can START, and no question is ever asked without a
 * clinician's sign-off. This changes navigation, not safety.
 *
 * Doctors remain reachable from the site footer on every page, from the Home
 * doctors section, and from each facility page - which is where that
 * relationship actually lives.
 */
const TABS = [
  { to: "/", key: "tab_home", Glyph: IconHospital, end: true },
  { to: "/search", key: "tab_facilities", Glyph: IconSearch },
  { to: "/care-guide", key: "tab_care_guide", Glyph: IconHeart },
  { to: "/visits", key: "tab_visits", Glyph: IconCalendar },
  { to: "/profile", key: "tab_profile", Glyph: IconUser },
] as const

export function BottomNav() {
  const { t } = useI18n()

  return (
    /* Hidden from `md` up. A thumb reaches the bottom of a phone; on a
       desktop it is a bar pinned to the bottom of a 1440px window carrying
       the same links already in the top bar. */
    <nav
      aria-label={t("nav_primary")}
      // Opaque for the same reason as the top bar: content scrolling
      // underneath a translucent tab bar ghosts through behind the labels.
      className="fixed inset-x-0 bottom-0 z-20 border-t border-n200 bg-white pb-[env(safe-area-inset-bottom)] md:hidden"
    >
      <ul className="mx-auto flex max-w-2xl">
        {TABS.map(({ to, key, Glyph, ...rest }) => (
          <li key={to} className="flex-1">
            <NavLink
              to={to}
              end={"end" in rest ? rest.end : undefined}
              className={({ isActive }) =>
                "flex h-14 flex-col items-center justify-center gap-1 px-1 transition-colors " +
                (isActive ? "text-primary" : "text-n700 active:text-n900")
              }
            >
              {({ isActive }) => (
                <>
                  {/* The active tab gets a tinted plate rather than only a
                      colour change: on a small screen at arm's length, a
                      shape reads faster than a hue, and it does not rely on
                      colour alone. */}
                  <span
                    className={
                      "flex h-7 w-12 items-center justify-center rounded-full transition-colors " +
                      (isActive ? "bg-primary-light" : "")
                    }
                  >
                    <Glyph size={20} />
                  </span>
                  <span
                    className={
                      "max-w-full truncate text-label leading-none " +
                      (isActive ? "font-semibold" : "")
                    }
                  >
                    {t(key)}
                  </span>
                </>
              )}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  )
}
