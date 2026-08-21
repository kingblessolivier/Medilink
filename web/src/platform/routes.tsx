import { Navigate, Route, Routes } from "react-router-dom"
import { Overview } from "./Overview"
import { Verification } from "./Verification"
import { TriageMonitor } from "./TriageMonitor"

/**
 * The platform portal.
 *
 * Loaded on demand from App.tsx. Django admin still owns CRUD on every model;
 * these three screens are the verification workflow, the platform aggregates
 * and the Care Guide monitoring that it cannot do.
 */
export function PlatformRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Overview />} />
      <Route path="/verification" element={<Verification />} />
      <Route path="/triage" element={<TriageMonitor />} />
      <Route path="*" element={<Navigate to="/platform" replace />} />
    </Routes>
  )
}
