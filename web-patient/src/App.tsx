import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { BrowserRouter, Route, Routes } from "react-router-dom"
import { I18nProvider } from "./i18n"
import { Home } from "./routes/Home"
import { Search } from "./routes/Search"
import { FacilityDetail } from "./routes/FacilityDetail"
import { OfflineBanner } from "./components/OfflineBanner"

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 2,
    },
  },
})

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <I18nProvider>
        <BrowserRouter>
          <OfflineBanner />
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/search" element={<Search />} />
            <Route path="/facility/:slug" element={<FacilityDetail />} />
          </Routes>
        </BrowserRouter>
      </I18nProvider>
    </QueryClientProvider>
  )
}
