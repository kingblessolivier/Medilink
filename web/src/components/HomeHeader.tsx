/**
 * S-04, the home dashboard header, per docs/01_patient_app.html.
 *
 * Green full-bleed, greeting and avatar, insurance chip, and a search field
 * that overlaps the bottom edge. The overlap is the point of the design - it
 * gives the first screen depth without a shadow or an illustration - and the
 * spec pins it at 16px.
 *
 * This reverses an earlier decision in the preset, which had reduced the hero
 * to a light wash on the reasoning that "green is not the interface". That
 * still holds everywhere else: green carries the primary action, availability
 * and verification, and nothing structural. The header is the deliberate
 * exception, because it is the one place the product introduces itself.
 *
 * WHAT THE CHIP MAY SAY. The design mock reads "Mutuelle de Sante - Active".
 * It does not say that here, and will not: MediLink knows which insurer a
 * patient has SELECTED, not whether their membership is paid up. "Active" is
 * a coverage claim we cannot support, and a patient turned away at a desk
 * after reading it does not make the distinction for us. The chip states the
 * chosen insurer and nothing more.
 */

import { Link } from "react-router-dom"
import { useI18n } from "../i18n"
import { Avatar } from "../ui/Avatar"
import {
  IconBell,
  IconCalendar,
  IconClock,
  IconHeart,
  IconShieldCheck,
  IconUser,
} from "../ui/icons"
import type { ReactNode } from "react"

type QuickAction = {
  to: string
  key: string
  Glyph: (props: { size?: number }) => ReactNode
  /** Tint for the tile's icon plate. */
  tone: string
}

/**
 * Four tiles, matching the spec. Deliberately not five: the row has to stay
 * one line at 360px, and in Kinyarwanda these labels wrap to two as it is.
 */
const ACTIONS: QuickAction[] = [
  { to: "/search", key: "book_appointment", Glyph: IconCalendar, tone: "bg-primary-light text-primary" },
  { to: "/queue", key: "track_queue", Glyph: IconClock, tone: "bg-accent/20 text-n900" },
  { to: "/care-guide", key: "check_symptoms", Glyph: IconHeart, tone: "bg-primary-light text-primary" },
  { to: "/visits", key: "my_records", Glyph: IconUser, tone: "bg-n100 text-n700" },
]

export function HomeHeader({
  name,
  insurerName,
  hasActiveAppointment,
  children,
}: {
  /** Null when signed out - the header greets without a name. */
  name: string | null
  /** The insurer the patient has chosen, not a coverage status. */
  insurerName: string | null
  /** The spec puts a bell here only when there is something to be notified about. */
  hasActiveAppointment: boolean
  /** The search field, which overlaps the header's bottom edge. */
  children: ReactNode
}) {
  const { t } = useI18n()

  return (
    <section className="relative">
      {/* pb-10 leaves room for the search field to sit over the boundary. */}
      <div className="bg-primary px-4 pb-10 pt-6 text-white sm:px-6">
        <div className="ml-shell">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="text-body text-white/80">{t("greeting")}</p>
              {name && (
                <p className="mt-0.5 truncate text-h2 font-semibold">{name}</p>
              )}

              {insurerName && (
                <span className="mt-2 inline-flex items-center gap-1.5 rounded-pill bg-white/15 px-3 py-1 text-label">
                  <IconShieldCheck size={14} />
                  {insurerName}
                </span>
              )}
            </div>

            <div className="flex shrink-0 items-center gap-2">
              {hasActiveAppointment && (
                <Link
                  to="/notifications"
                  aria-label={t("nav_notifications")}
                  className="grid h-touch w-touch place-items-center rounded-full text-white/90 hover:bg-white/10"
                >
                  <IconBell size={20} />
                </Link>
              )}
              {name && (
                <Link to="/profile" aria-label={t("nav_profile")}>
                  {/* White-on-green rather than the default green-on-tint:
                      the usual Avatar palette disappears against this header. */}
                  <Avatar
                    name={name}
                    size="md"
                    className="!bg-white/20 font-medium !text-white"
                  />
                </Link>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* The 16px overlap. -mt-6 lifts the field over the green edge; the
          spec calls this out explicitly as what creates the depth. */}
      <div className="relative -mt-6 px-4 sm:px-6">
        <div className="ml-shell">{children}</div>
      </div>

      <div className="ml-shell mt-6 px-4 sm:px-6">
        <h2 className="ml-label mb-3">{t("quick_actions")}</h2>
        <ul className="grid grid-cols-4 gap-2">
          {ACTIONS.map(({ to, key, Glyph, tone }) => (
            <li key={key}>
              <Link
                to={to}
                className="flex h-full min-h-touch flex-col items-center gap-2 rounded-lg border border-n200 bg-white p-3 text-center transition-colors hover:border-n300"
              >
                <span
                  className={`grid h-9 w-9 shrink-0 place-items-center rounded-lg ${tone}`}
                >
                  <Glyph size={18} />
                </span>
                {/* Allowed to wrap to two lines: Kinyarwanda needs it, and a
                    truncated verb here reads as a different word. */}
                <span className="text-label leading-tight text-n700">
                  {t(key)}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}

export default HomeHeader
