import { lazy, Suspense } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { BrowserRouter, Route, Routes, useLocation } from "react-router-dom"
import { I18nProvider } from "./i18n"
import { AuthProvider } from "./hooks/useAuth"
import { Home } from "./routes/Home"
import { FindCare } from "./routes/FindCare"
import { CareGuide } from "./routes/CareGuide"
// Lazily loaded: it is a developer tool, and 2.2 KB of it has no
// business in the bundle a patient downloads on a 2G connection.
// Still reachable on a deployed preview, which is where checking
// that a deploy is styled correctly actually matters.
const Gallery = lazy(() =>
  import("./routes/Gallery").then((m) => ({ default: m.Gallery })),
)
import { Compare } from "./routes/Compare"
import { Doctors } from "./routes/Doctors"
import { DoctorProfile } from "./routes/DoctorProfile"
import { ServiceDetail } from "./routes/ServiceDetail"
import { AppointmentDetail } from "./routes/AppointmentDetail"
import { QueueTracking } from "./routes/QueueTracking"
import { Notifications } from "./routes/Notifications"
import { FacilityDetail } from "./routes/FacilityDetail"
import { SignIn } from "./routes/SignIn"
import { Book } from "./routes/Book"
import { Visits } from "./routes/Visits"
import { Profile } from "./routes/Profile"
import { OfflineBanner } from "./components/OfflineBanner"
import { BottomNav } from "./components/BottomNav"

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 2,
    },
  },
})

/** The nav is a distraction on the sign-in screen. */
function Chrome() {
  const { pathname } = useLocation()
  return pathname === "/sign-in" ? null : <BottomNav />
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <I18nProvider>
        <BrowserRouter>
          <AuthProvider>
            <OfflineBanner />
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/search" element={<FindCare />} />
              {/* Reachable by URL even when the gate is shut - the screen
                  explains why rather than 404ing on a feature that exists. */}
              <Route path="/care-guide" element={<CareGuide />} />
              {/* Developer tool. Not linked, not in the nav, no patient data
                  and no API calls - it just has to live at a URL to be
                  lookable-at. See routes/Gallery.tsx for why it exists. */}
              <Route
                path="/_gallery"
                element={
                  <Suspense fallback={<p className="p-6 text-body">Loading...</p>}>
                    <Gallery />
                  </Suspense>
                }
              />
              <Route path="/compare" element={<Compare />} />
              <Route path="/doctors" element={<Doctors />} />
              <Route path="/doctor/:slug" element={<DoctorProfile />} />
              <Route path="/service/:code" element={<ServiceDetail />} />
              <Route path="/appointment/:id" element={<AppointmentDetail />} />
              <Route path="/queue" element={<QueueTracking />} />
              <Route path="/notifications" element={<Notifications />} />
              <Route path="/facility/:slug" element={<FacilityDetail />} />
              <Route path="/facility/:slug/book" element={<Book />} />
              <Route path="/sign-in" element={<SignIn />} />
              <Route path="/visits" element={<Visits />} />
              <Route path="/profile" element={<Profile />} />
            </Routes>
            <Chrome />
          </AuthProvider>
        </BrowserRouter>
      </I18nProvider>
    </QueryClientProvider>
  )
}
