import { Navigate, Route, Routes } from "react-router-dom"
import { useAuth } from "../hooks/useAuth"
import { DashboardShell, type NavSection } from "../components/DashboardShell"
import {
  IconCalendar,
  IconChart,
  IconClock,
  IconHospital,
  IconShield,
  IconSearch,
  IconInfo,
  IconStethoscope,
  IconUsers,
} from "../ui/icons"
import { useQueueActions } from "./useQueueActions"
import { Reception } from "./Reception"
import { WorkspaceDashboard } from "./Dashboard"
import { WorkspaceClinic } from "./Clinic"
import { WorkspaceTeam } from "./Team"
import { WorkspaceAppointments } from "./Appointments"
import { WorkspaceDoctors } from "./Doctors"
import { WorkspaceServices } from "./Services"
import { WorkspaceReports } from "./Reports"
import { WorkspaceSchedule } from "./Schedule"
import { WorkspaceInsurance } from "./Insurance"
import { WorkspaceSettings } from "./Settings"
import { WorkspacePatients } from "./Patients"
import { Security } from "./Security"
import { useI18n } from "../i18n"

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
    label: "ws_today_now",
    items: [
      { to: "/workspace", label: "nav_reception", icon: <IconUsers size={17} />, end: true },
      { to: "/workspace/dashboard", label: "ws_nav_dashboard", icon: <IconChart size={17} /> },
      { to: "/workspace/appointments", label: "nav_appointments", icon: <IconCalendar size={17} /> },
      { to: "/workspace/clinic", label: "nav_clinic", icon: <IconStethoscope size={17} /> },
      { to: "/workspace/patients", label: "nav_find_patient", icon: <IconSearch size={17} /> },
    ],
  },
  {
    label: "nav_facilities",
    items: [
      { to: "/workspace/schedule", label: "nav_schedule", icon: <IconClock size={17} /> },
      { to: "/workspace/doctors", label: "nav_doctors", icon: <IconStethoscope size={17} /> },
      { to: "/workspace/services", label: "nav_services", icon: <IconHospital size={17} /> },
      { to: "/workspace/insurance", label: "nav_insurance", icon: <IconShield size={17} /> },
      { to: "/workspace/reports", label: "nav_reports", icon: <IconChart size={17} /> },
      { to: "/workspace/team", label: "nav_staff_accounts", icon: <IconUsers size={17} /> },
      { to: "/workspace/settings", label: "nav_settings", icon: <IconInfo size={17} /> },
    ],
  },
]

export function WorkspaceRoutes() {
  const { t } = useI18n()
  const { session } = useAuth()
  const actions = useQueueActions()

  if (session.state !== "signed_in") return null

  return (
    <DashboardShell
      title={t("nav_workspace")}
      subtitle={session.session.facility?.name ?? ""}
      sections={[...SECTIONS.map(section => ({ ...section, label: t(section.label), items: section.items.map(item => ({ ...item, label: t(item.label) })) })), { label: t("security_title"), items: [{ to: "/workspace/security", label: t("security_title"), icon: <IconShield size={17} /> }] }]}
    >
      <Routes>
        <Route path="/security" element={<Security />} />
        <Route path="/" element={<Reception actions={actions} />} />
        {/* FA-01. Not the workspace landing: a receptionist opening this app
            needs the queue in front of them, and the desk is what most people
            signing in are here to work. The overview is one click away. */}
        <Route path="/dashboard" element={<WorkspaceDashboard />} />
        {/* CL-01 and CL-02. Read-only: clinicians cannot manage the queue. */}
        <Route path="/clinic" element={<WorkspaceClinic />} />
        {/* FA-10. Administrators only - the API refuses everyone else, and
            the screen says which refusal it got. */}
        <Route path="/team" element={<WorkspaceTeam />} />
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
        <Route path="/patients" element={<WorkspacePatients />} />
        <Route
          path="/settings"
          element={
            <WorkspaceSettings canManage={session.session.can_manage_queue} />
          }
        />
        <Route path="/reports" element={<WorkspaceReports />} />
        <Route path="*" element={<Navigate to="/workspace" replace />} />
      </Routes>
    </DashboardShell>
  )
}
