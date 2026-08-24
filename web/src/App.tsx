import { lazy, Suspense, type ReactNode } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
  useLocation,
} from "react-router-dom"
import { I18nProvider, useI18n } from "./i18n"
import { AuthProvider, useAuth } from "./hooks/useAuth"
import type { SessionKind } from "./api/types"

// -------------------------------------------------------------- patient
import { Home } from "./routes/Home"
import { FindCare } from "./routes/FindCare"
import { Doctors } from "./routes/Doctors"


import { ErrorBoundary } from "./components/ErrorBoundary"
import { OfflineBanner } from "./components/OfflineBanner"
import { BottomNav } from "./components/BottomNav"
import { TopNav, homeFor } from "./components/TopNav"
import { Notice } from "./ui"


// Split from the cold load.
//
// Home, FindCare and Doctors are where a first-time visitor lands; everything
// below is a tap away. A tap can afford a chunk fetch - it cannot afford
// being parsed on a cheap phone before the first screen paints. Measured on
// 3G with a 4x CPU throttle, which is roughly a low-end Android.
const CareGuide = lazy(() =>
  import("./routes/CareGuide").then((m) => ({ default: m.CareGuide })),
)
const Compare = lazy(() =>
  import("./routes/Compare").then((m) => ({ default: m.Compare })),
)
const DoctorProfile = lazy(() =>
  import("./routes/DoctorProfile").then((m) => ({ default: m.DoctorProfile })),
)
const ServiceDetail = lazy(() =>
  import("./routes/ServiceDetail").then((m) => ({ default: m.ServiceDetail })),
)
const AppointmentDetail = lazy(() =>
  import("./routes/AppointmentDetail").then((m) => ({ default: m.AppointmentDetail })),
)
const QueueTracking = lazy(() =>
  import("./routes/QueueTracking").then((m) => ({ default: m.QueueTracking })),
)
const Notifications = lazy(() =>
  import("./routes/Notifications").then((m) => ({ default: m.Notifications })),
)
const FacilityDetail = lazy(() =>
  import("./routes/FacilityDetail").then((m) => ({ default: m.FacilityDetail })),
)
const Book = lazy(() =>
  import("./routes/Book").then((m) => ({ default: m.Book })),
)
const Visits = lazy(() =>
  import("./routes/Visits").then((m) => ({ default: m.Visits })),
)
const Profile = lazy(() =>
  import("./routes/Profile").then((m) => ({ default: m.Profile })),
)
const SignIn = lazy(() =>
  import("./routes/SignIn").then((m) => ({ default: m.SignIn })),
)
const Register = lazy(() =>
  import("./routes/Register").then((m) => ({ default: m.Register })),
)
const Privacy = lazy(() =>
  import("./routes/Privacy").then((m) => ({ default: m.Privacy })),
)

// A developer tool. 2.7 KB of it has no business in the bundle somebody
// downloads on a 2G connection, so it is split out and left out of the
// service worker's precache. See routes/Gallery.tsx for why it exists.
const Gallery = lazy(() =>
  import("./routes/Gallery").then((m) => ({ default: m.Gallery })),
)

function Loading() {
  const { t } = useI18n()
  return <p className="p-6 text-body text-ink-muted">{t("loading")}</p>
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 2,
    },
  },
})

/**
 * A route only a given kind of user may see.
 *
 * This decides which SCREENS to render and nothing else. Every endpoint behind
 * them re-checks on the server - a guard here is a courtesy to the person
 * using the app, never a security control. Removing it would make the UI
 * confusing; it would not make anything reachable that is not already refused.
 */
function Require({
  kind,
  children,
}: {
  kind: SessionKind
  children: ReactNode
}) {
  const { session } = useAuth()
  const { t } = useI18n()
  const location = useLocation()

  if (session.state === "loading") {
    return <p className="p-6 text-body text-ink-muted">{t("loading")}</p>
  }

  if (session.state === "anonymous") {
    // Carry where they were going, so signing in lands them there rather than
    // on a home page they then have to navigate away from.
    return (
      <Navigate
        to={`/sign-in?next=${encodeURIComponent(location.pathname)}`}
        replace
      />
    )
  }

  if (session.session.kind !== kind) {
    // Signed in, wrong kind. NOT a redirect to sign-in: they are already
    // signed in, and bouncing them to a form that will succeed and send them
    // straight back here is a loop, not an answer.
    return (
      <div className="mx-auto max-w-md px-4 py-10">
        <h1 className="text-h2">{t("auth_wrong_surface_title")}</h1>
        <div className="mt-4">
          <Notice tone="info">{t("auth_wrong_surface_body")}</Notice>
        </div>
        <a className="ml-btn-primary mt-4" href={homeFor(session.session)}>
          {t("auth_go_to_your_area")}
        </a>
      </div>
    )
  }

  return <>{children}</>
}

/**
 * The two staff surfaces load on demand.
 *
 * One app now carries the patient screens, a reception desk and a platform
 * portal. Most people who open it are patients on a phone, and shipping them
 * the admin portal to download and parse is a cost they never get anything
 * for. Split here rather than per-screen: somebody who reaches the workspace
 * wants all of it within seconds, so five chunks would be five round trips.
 */
const WorkspaceRoutes = lazy(() =>
  import("./workspace/routes").then((m) => ({ default: m.WorkspaceRoutes })),
)

const PlatformRoutes = lazy(() =>
  import("./platform/routes").then((m) => ({ default: m.PlatformRoutes })),
)

/**
 * The bottom nav is a patient-surface, small-screen affordance only.
 *
 * A thumb reaches the bottom of a phone and not the top, which is why patients
 * get it. Staff and admins are at a desk with the top bar in reach, and the
 * auth screens want nothing competing with the form.
 */
function Chrome() {
  const { pathname } = useLocation()
  const { session } = useAuth()

  const onAuthScreen = pathname === "/sign-in" || pathname === "/register"
  const onStaffSurface =
    pathname.startsWith("/workspace") || pathname.startsWith("/platform")

  if (onAuthScreen || onStaffSurface) return null
  if (session.state === "signed_in" && session.session.kind !== "patient") {
    return null
  }
  return <BottomNav />
}

function Shell() {
  const { session, signOut } = useAuth()
  const { pathname } = useLocation()
  const current = session.state === "signed_in" ? session.session : null

  return (
    <>
      <OfflineBanner />
      <TopNav session={current} onSignOut={signOut} />

      {/* Keyed on the path so navigating away from a broken screen
          recovers, instead of staying stuck until a reload. */}
      <ErrorBoundary level="route" resetKey={pathname}>
      <Suspense fallback={<Loading />}>
      <Routes>
        {/* ---------------------------------------------------- patient */}
        <Route path="/" element={<Home />} />
        <Route path="/search" element={<FindCare />} />
        {/* Reachable by URL even when the clinical gate is shut - the screen
            explains why rather than 404ing on a feature that exists. */}
        <Route path="/care-guide" element={<CareGuide />} />
        <Route path="/compare" element={<Compare />} />
        <Route path="/doctors" element={<Doctors />} />
        <Route path="/doctor/:slug" element={<DoctorProfile />} />
        <Route path="/service/:code" element={<ServiceDetail />} />
        <Route path="/appointment/:id" element={<AppointmentDetail />} />
        <Route path="/queue" element={<QueueTracking />} />
        <Route path="/notifications" element={<Notifications />} />
        <Route path="/facility/:slug" element={<FacilityDetail />} />
        <Route path="/facility/:slug/book" element={<Book />} />
        <Route path="/visits" element={<Visits />} />
        <Route path="/profile" element={<Profile />} />

        {/* ------------------------------------------------------- auth */}
        <Route path="/sign-in" element={<SignIn />} />
        <Route path="/register" element={<Register />} />
        {/* Linked from the consent checkbox. Consenting to a notice that
            does not exist is not consent. */}
        <Route path="/privacy" element={<Privacy />} />

        {/* -------------------------------------------------- workspace */}
        <Route
          path="/workspace/*"
          element={
            <Require kind="staff">
              <Suspense fallback={<Loading />}>
                <WorkspaceRoutes />
              </Suspense>
            </Require>
          }
        />

        {/* --------------------------------------------------- platform */}
        <Route
          path="/platform/*"
          element={
            <Require kind="admin">
              <Suspense fallback={<Loading />}>
                <PlatformRoutes />
              </Suspense>
            </Require>
          }
        />

        {/* Developer tool. Not linked and not in the nav; it just has to live
            at a URL to be lookable-at. */}
        <Route
          path="/_gallery"
          element={
            <Suspense fallback={<Loading />}>
              <Gallery />
            </Suspense>
          }
        />

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      </Suspense>
      </ErrorBoundary>

      <Chrome />
    </>
  )
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <I18nProvider>
        <BrowserRouter>
          {/* Inside I18nProvider so the recovery screen can be translated,
              outside AuthProvider so a failure in the session lookup still
              renders something a person can act on. */}
          <ErrorBoundary level="app">
            <AuthProvider>
              <Shell />
            </AuthProvider>
          </ErrorBoundary>
        </BrowserRouter>
      </I18nProvider>
    </QueryClientProvider>
  )
}
