import { Navigate, Route, Routes } from "react-router-dom"
import { useAuth } from "../hooks/useAuth"
import { useQueueActions } from "./useQueueActions"
import { Reception } from "./Reception"
import { WorkspaceAppointments } from "./Appointments"
import { WorkspaceDoctors } from "./Doctors"
import { WorkspaceServices } from "./Services"
import { WorkspaceReports } from "./Reports"

/**
 * The facility workspace.
 *
 * Loaded on demand from App.tsx - a patient on a phone has no use for a
 * reception desk and should not be downloading one.
 *
 * `useQueueActions` is called HERE rather than inside Reception so the offline
 * queue survives navigation: a receptionist who checks somebody in, looks at
 * the appointment list and comes back must not find their pending actions
 * gone.
 */
export function WorkspaceRoutes() {
  const { session } = useAuth()
  const actions = useQueueActions()

  if (session.state !== "signed_in") return null

  return (
    <Routes>
      <Route path="/" element={<Reception actions={actions} />} />
      <Route
        path="/appointments"
        element={
          <WorkspaceAppointments canManage={session.session.can_manage_queue} />
        }
      />
      <Route path="/doctors" element={<WorkspaceDoctors />} />
      <Route path="/services" element={<WorkspaceServices />} />
      <Route path="/reports" element={<WorkspaceReports />} />
      <Route path="*" element={<Navigate to="/workspace" replace />} />
    </Routes>
  )
}
