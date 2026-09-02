import { Link } from "react-router-dom"
import { useI18n } from "../i18n"
import { IconPhone } from "../ui/icons"

/**
 * The end of the page, on every patient screen.
 *
 * There was no footer anywhere in this product. On a phone the bottom nav
 * hides that - there is always a bar under your thumb - but on a desktop the
 * page simply stopped, with no way to reach the privacy notice from anywhere
 * except the registration form.
 *
 * **The emergency number is the reason this earns its space.** `912` already
 * existed in the translation bundle, used in exactly one place: the Care
 * Guide. The Care Guide is behind the clinical gate and returns 503, and the
 * UI hides its entry points - so the emergency number was, in practice,
 * unreachable to every patient using MediLink. A health product cannot have
 * its emergency number live inside a feature that is switched off.
 *
 * It is first, before the navigation, and it is a `tel:` link so one tap
 * dials. Somebody who needs it is not going to read the rest of this.
 *
 * What is deliberately NOT here: a newsletter sign-up, and testimonials.
 * Collecting an email for no stated purpose runs against the data
 * minimisation in docs/08, and MediLink has no patients yet - manufacturing
 * social proof for a health service is the kind of thing this codebase
 * refuses everywhere else, which is why there are no ratings on a doctor
 * either. Real numbers can go here when there are real numbers.
 */
export function SiteFooter() {
  const { t } = useI18n()
  const emergency = t("emergency_number")

  return (
    // `mt-auto` is not used: the page is not a flex column, and a footer that
    // floats to the bottom of a short viewport reads as a fixed bar. It ends
    // the content instead.
    <footer className="mt-12 border-t border-n200 bg-n100">
      {/* `pb-24` on a phone, not `py-8`. The bottom nav is fixed and floats
          OVER this - and the pb-24 that routes carry is on the route content,
          which the footer sits outside of. Without its own clearance the last
          line ends up 25px behind the nav bar. */}
      <div className="ml-shell pt-8 pb-24 md:pb-8">
        {/* Emergency first, and unmissable. Not a link among links. */}
        {/* Compact, and it stops where its content stops. Stretched to the
            full 88rem shell it became a pink band across the bottom of every
            page - loud enough to read as a site-wide error state, which is
            the opposite of what an emergency affordance should feel like on
            a page nobody is panicking on. Constrained, it is still the first
            and most contrasting thing in the footer. */}
        <a
          href={`tel:${emergency}`}
          className="inline-flex w-full max-w-sm items-center gap-3 rounded-lg border border-danger/30 bg-danger/10 p-3 text-n900 no-underline transition-colors hover:bg-danger/10/70"
        >
          <span className="ml-icon-plate bg-danger text-white">
            <IconPhone size={18} />
          </span>
          <span className="min-w-0">
            <span className="block text-body text-n700">
              {t("footer_emergency_label")}
            </span>
            <span className="block text-body-lg font-semibold text-danger">
              {t("footer_emergency_action", { number: emergency })}
            </span>
          </span>
        </a>

        <div className="mt-8 grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <p className="text-h3 text-primary">MediLink</p>
            <p className="mt-1 max-w-prose text-body text-n700">
              {t("footer_tagline")}
            </p>
          </div>

          <nav aria-label={t("footer_explore")}>
            <p className="text-label uppercase tracking-wide text-n600">
              {t("footer_explore")}
            </p>
            <ul className="mt-3 space-y-2">
              <FooterLink to="/search">{t("nav_facilities")}</FooterLink>
              <FooterLink to="/doctors">{t("nav_doctors")}</FooterLink>
              {/* The brief lists Services in the primary nav, but that is
                  already at its five-item limit and Find Care is the more
                  common entry. It gets a destination here instead. */}
              <FooterLink to="/services">{t("services_all")}</FooterLink>
              <FooterLink to="/insurance">{t("nav_insurance")}</FooterLink>
              <FooterLink to="/compare">{t("compare")}</FooterLink>
            </ul>
          </nav>

          <nav aria-label={t("footer_your_account")}>
            <p className="text-label uppercase tracking-wide text-n600">
              {t("footer_your_account")}
            </p>
            <ul className="mt-3 space-y-2">
              <FooterLink to="/visits">{t("nav_visits")}</FooterLink>
              <FooterLink to="/profile">{t("nav_profile")}</FooterLink>
            </ul>
          </nav>

          {/* Support was folded into "Your account", which left one column
              carrying five unrelated links and the brand column spanning half
              the footer with a single sentence in it. Four columns of roughly
              equal weight read as a structure rather than as leftovers. */}
          <nav aria-label={t("footer_support")}>
            <p className="text-label uppercase tracking-wide text-n600">
              {t("footer_support")}
            </p>
            <ul className="mt-3 space-y-2">
              <FooterLink to="/help">{t("help_title")}</FooterLink>
              <FooterLink to="/about">{t("about_title")}</FooterLink>
              <FooterLink to="/privacy">{t("footer_privacy_link")}</FooterLink>
            </ul>
          </nav>
        </div>

        {/* Says what this is and, more importantly, what it is not. */}
        <p className="mt-8 border-t border-n200 pt-6 text-body text-n700">
          {t("footer_not_medical_advice")}
        </p>
      </div>
    </footer>
  )
}

function FooterLink({ to, children }: { to: string; children: React.ReactNode }) {
  return (
    <li>
      {/* min-h-touch: these sit close together, and a column of footer links on a phone
          is where mis-taps happen. */}
      <Link
        to={to}
        className="inline-flex min-h-touch items-center text-body-lg text-n700 hover:text-primary hover:underline"
      >
        {children}
      </Link>
    </li>
  )
}
