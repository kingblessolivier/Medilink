import { Navigate, Route, Routes } from "react-router-dom"
import { useAuth } from "../hooks/useAuth"
import { DashboardShell, type NavSection } from "../components/DashboardShell"
import {
  IconCalendar,
  IconChart,
  IconClock,
  IconHospital,
  IconShield,
  IconStethoscope,
  IconUsers,
} from "../ui/icons"
import { useQueueActions } from "./useQueueActions"
import { Reception } from "./Reception"
import { WorkspaceAppointments } from "./Appointments"
import { WorkspaceDoctors } from "./Doctors"
import { WorkspaceServices } from "./Services"
import { WorkspaceReports } from "./Reports"
import { WorkspaceSchedule } from "./Schedule"
import { WorkspaceInsurance } from "./Insurance"

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
/**
 * Two groups, because the day splits that way: what is happening at the desk
 * right now, and the reference material behind it.
 */
const SECTIONS: NavSection[] = [
  {
    label: "Today",
    items: [
      { to: "/workspace", label: "Reception", icon: <IconUsers size={17} />, end: true },
      { to: "/workspace/appointments", label: "Appointments", icon: <IconCalendar size={17} /> },
    ],
  },
  {
    label: "Facility",
    items: [
      { to: "/workspace/schedule", label: "Schedule", icon: <IconClock size={17} /> },
      { to: "/workspace/doctors", label: "Doctors", icon: <IconStethoscope size={17} /> },
      { to: "/workspace/services", label: "Services", icon: <IconHospital size={17} /> },
      { to: "/workspace/insurance", label: "Insurance", icon: <IconShield size={17} /> },
      { to: "/workspace/reports", label: "Reports", icon: <IconChart size={17} /> },
    ],
  },
]

export function WorkspaceRoutes() {
  const { session } = useAuth()
  const actions = useQueueActions()

  if (session.state !== "signed_in") return null

  return (
    <DashboardShell
      title="Workspace"
      subtitle={session.session.facility?.name ?? ""}
      sections={SECTIONS}
    >
      <Routes>
        <Route path="/" element={<Reception actions={actions} />} />
        <Route
          path="/appointments"
          element={
            <WorkspaceAppointments
              canManage={session.session.can_manage_queue}
            />
          }
        />
        <Route
          path="/schedule"
          element={
            <WorkspaceSchedule canManage={session.session.can_manage_queue} />
          }
        />
        <Route path="/doctors" element={<WorkspaceDoctors />} />
        <Route path="/services" element={<WorkspaceServices />} />
        <Route
          path="/insurance"
          element={
            <WorkspaceInsurance canManage={session.session.can_manage_queue} />
          }
        />
        <Route path="/reports" element={<WorkspaceReports />} />
        <Route path="*" element={<Navigate to="/workspace" replace />} />
      </Routes>
    </DashboardShell>
  )
}
