import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { BrowserRouter, Route, Routes, useLocation } from "react-router-dom"
import { I18nProvider } from "./i18n"
import { AuthProvider } from "./hooks/useAuth"
import { Home } from "./routes/Home"
import { FindCare } from "./routes/FindCare"
import { CareGuide } from "./routes/CareGuide"
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
