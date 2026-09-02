/**
 * S-01 splash and S-02 onboarding, per docs/01_patient_app.html.
 *
 * One route rather than two: the spec draws them as separate screens, but Skip
 * on any slide and Get started on the splash both land in the same place, and
 * a patient who has seen this once must never see it again. Keeping the state
 * in one component means the "seen it" flag is written once, on the way out.
 *
 * WHO ACTUALLY SEES IT. The spec labels S-01 "Splash / Landing", and App
 * redirects "/" here to honour that - but only for a signed-out visitor who
 * has not been through it before. Three things fall out of that, all of them
 * the point: a WhatsApp link straight to a facility or a queue still opens
 * where it points, because only the bare "/" redirects; a returning patient
 * reopening the PWA in a waiting room gets the product rather than an
 * introduction; and nobody sees it twice, because the flag is written on the
 * way out. `lib/welcomeSeen` holds that flag, deliberately apart from this
 * module so App can read it without pulling this screen into the main bundle.
 *
 * THE USSD HINT IS NEVER HIDDEN. It is the whole point of the screen for the
 * patients this product is least able to reach otherwise - somebody on a
 * feature phone reading over a friend's shoulder. The spec says "always
 * visible - never hidden for low-tech users", and it means on every slide.
 */

import { useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { useI18n } from "../i18n"
import { LanguageToggle } from "../components/LanguageToggle"
import { IconClock, IconHeart, IconSearch } from "../ui/icons"
import { markWelcomeSeen as markSeen } from "../lib/welcomeSeen"

/** The shortcode is one string in one place: it is printed on posters. */
const USSD_CODE = "*182*1#"

const SLIDES = [
  { title: "onb1_title", body: "onb1_body", Glyph: IconSearch },
  { title: "onb2_title", body: "onb2_body", Glyph: IconClock },
  { title: "onb3_title", body: "onb3_body", Glyph: IconHeart },
] as const

export function Welcome() {
  const { t } = useI18n()
  const navigate = useNavigate()
  // -1 is the splash; 0..2 are the onboarding slides.
  const [slide, setSlide] = useState(-1)

  const leave = (to: string) => {
    markSeen()
    navigate(to)
  }

  if (slide === -1) {
    return (
      <div className="flex min-h-[100dvh] flex-col bg-primary px-6 pb-10 pt-4 text-white">
        <div className="flex justify-end">
          <LanguageToggle />
        </div>

        <div className="flex flex-1 flex-col items-center justify-center text-center">
          {/* 80x80 white card, 20px radius, green mark - the spec's logo. */}
          <span className="grid h-20 w-20 place-items-center rounded-[20px] bg-white text-primary">
            <IconClock size={38} />
          </span>
          <h1 className="mt-6 text-h1">MediLink</h1>
          <p className="mt-3 text-body-lg text-white/90">
            {t("splash_tagline")}
          </p>
          <p className="text-body-lg text-white/90">{t("splash_sub")}</p>
        </div>

        <div className="w-full">
          {/* White fill, green text, full width - the spec's CTA. */}
          <button
            className="min-h-touch w-full rounded-pill bg-white px-6 text-body-lg font-bold text-primary active:scale-[0.97]"
            onClick={() => setSlide(0)}
          >
            {t("get_started")}
          </button>

          <p className="mt-4 text-center">
            <Link
              to="/sign-in"
              onClick={markSeen}
              className="inline-flex min-h-touch items-center text-body-lg text-white underline"
            >
              {t("have_account")}
            </Link>
          </p>

          <p className="mt-4 rounded-md bg-white/10 px-4 py-3 text-center text-body text-white/90">
            {t("ussd_hint", { code: USSD_CODE })}
          </p>
        </div>
      </div>
    )
  }

  const { title, body, Glyph } = SLIDES[slide]
  const last = slide === SLIDES.length - 1

  return (
    <div className="flex min-h-[100dvh] flex-col bg-white px-6 pb-10 pt-4">
      <div className="flex items-center justify-between gap-4">
        {/* Three segments, 3px, the active one primary. A dot row would not
            say how far through you are; segments do. */}
        <ol className="flex flex-1 gap-2" aria-label={`${slide + 1} / ${SLIDES.length}`}>
          {SLIDES.map((s, i) => (
            <li
              key={s.title}
              aria-current={i === slide ? "step" : undefined}
              className={`h-[3px] flex-1 rounded-sm ${
                i <= slide ? "bg-primary" : "bg-n200"
              }`}
            />
          ))}
        </ol>
        <LanguageToggle />
      </div>

      <div className="flex flex-1 flex-col justify-center">
        {/* 200px illustration area, primary-light, drawn not photographed:
            stock imagery of smiling clinicians is the visual language of
            marketing, and this is a tool people open when they are unwell. */}
        <div className="grid h-[200px] place-items-center rounded-lg bg-primary-light text-primary">
          <Glyph size={56} />
        </div>

        <h1 className="mt-8 text-h1 text-n900">{t(title)}</h1>
        <p className="mt-3 text-body-lg text-n700">{t(body)}</p>
      </div>

      <div className="flex items-center justify-between gap-3">
        <button
          className="ml-btn-ghost text-n700"
          onClick={() => leave("/sign-in")}
        >
          {t("onb_skip")}
        </button>
        <button
          className="ml-btn-primary flex-1"
          onClick={() => (last ? leave("/sign-in") : setSlide(slide + 1))}
        >
          {last ? t("get_started") : t("onb_next")}
        </button>
      </div>

      <p className="mt-4 text-center text-body text-n600">
        {t("ussd_hint", { code: USSD_CODE })}
      </p>
    </div>
  )
}

export default Welcome
