import { Component, type ErrorInfo, type ReactNode } from "react"
import { Link } from "react-router-dom"
import { useI18n } from "../i18n"

/**
 * Catches a render error instead of letting it blank the app.
 *
 * There were none of these anywhere in `web/src`, and React says so in the
 * console when it happens. One unguarded array read in a card component -
 * `doctor.specialties.length` on a record where the field was absent - took
 * out the header, the bottom nav and every route with it, leaving a white
 * page and no way back except knowing to reload. For a health service used
 * on unreliable connections that is the worst possible failure mode, because
 * it is indistinguishable from the app being broken for everyone.
 *
 * Two levels are used, and the second is the one that matters day to day:
 *
 *   `level="app"`   wraps the router. The catastrophic case.
 *   `level="route"` wraps each screen, so a broken facility card does not
 *                   take out the queue screen a patient is mid-journey on.
 *
 * `resetKey` re-mounts the subtree when it changes - the route path, in
 * practice - so navigating away from a broken screen recovers rather than
 * staying stuck on the error until a reload.
 */

type Props = {
  children: ReactNode
  level?: "app" | "route"
  resetKey?: string
}

type State = { error: Error | null }

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidUpdate(previous: Props) {
    if (this.state.error && previous.resetKey !== this.props.resetKey) {
      this.setState({ error: null })
    }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Kept to the console deliberately. There is no error-reporting service
    // wired up, and posting a stack trace containing patient data to one
    // would need a decision in docs/08 before it happened, not after.
    console.error("Unhandled render error", error, info.componentStack)
  }

  render() {
    if (!this.state.error) return this.props.children
    return (
      <ErrorScreen
        level={this.props.level ?? "route"}
        onRetry={() => this.setState({ error: null })}
      />
    )
  }
}

/**
 * The recovery screen. Split out as a function component so it can use the
 * translation hook - a class cannot, and an error page in the wrong language
 * is barely better than a blank one.
 */
function ErrorScreen({
  level,
  onRetry,
}: {
  level: "app" | "route"
  onRetry: () => void
}) {
  const { t } = useI18n()

  return (
    <div
      role="alert"
      className="mx-auto w-full max-w-sm px-4 py-16 text-center"
    >
      <h1 className="text-h2 text-n900">{t("error_screen_title")}</h1>
      <p className="mt-2 text-body-lg text-n700">{t("error_screen_body")}</p>

      <div className="mt-6 flex flex-col gap-3">
        {/* Re-mounts the subtree rather than reloading the page: a reload
            would also discard anything the reception client has queued
            offline and not yet synced. */}
        <button className="ml-btn-primary w-full" onClick={onRetry}>
          {t("error_screen_retry")}
        </button>

        {/* The bottom nav is part of what disappears when the app-level
            boundary fires, so the way out has to be on this screen. A full
            navigation, not a router link, because the router may be what
            failed. */}
        {level === "app" ? (
          <a className="ml-btn-secondary w-full" href="/">
            {t("error_screen_home")}
          </a>
        ) : (
          <Link className="ml-btn-secondary w-full" to="/">
            {t("error_screen_home")}
          </Link>
        )}
      </div>
    </div>
  )
}
