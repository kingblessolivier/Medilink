import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { BrowserRouter, Route, Routes, useLocation } from "react-router-dom"
import { I18nProvider } from "./i18n"
import { AuthProvider } from "./hooks/useAuth"
import { Home } from "./routes/Home"
import { Search } from "./routes/Search"
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
              <Route path="/search" element={<Search />} />
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
