import { Navigate, Route, Routes } from "react-router-dom"
import { useAuth } from "../hooks/useAuth"
import { DashboardShell, type NavSection } from "../components/DashboardShell"
import {
  IconAlert,
  IconChart,
  IconGlobe,
  IconHeart,
  IconHospital,
  IconShield,
  IconShieldCheck,
  IconInfo,
  IconStethoscope,
} from "../ui/icons"
import { Overview } from "./Overview"
import { Verification } from "./Verification"
import { TriageMonitor } from "./TriageMonitor"
import { PlatformInsurers } from "./Insurers"
import { PlatformSettings } from "./Settings"
import { PlatformFacilities } from "./Facilities"
import { PlatformProviders } from "./Providers"
import { PlatformAccess } from "./Access"
import { PlatformActivity } from "./Activity"

/**
 * The platform portal.
 *
 * Nine sections in three groups. A flat list of nine is a menu somebody has
 * to read; grouped, it is a map - and the grouping says what the surface is
 * for:
 *
 *   OVERSIGHT   what is happening, and is anything wrong
 *   DIRECTORY   what exists on the platform
 *   GOVERNANCE  who approved what, and who read what
 *
 * Django admin still owns CRUD on every model. Nothing here edits a record
 * except verification, which needs a note saying what was checked.
 */
const SECTIONS: NavSection[] = [
  {
    label: "Oversight",
    items: [
      { to: "/platform", label: "Overview", icon: <IconGlobe size={17} />, end: true },
      { to: "/platform/activity", label: "Activity", icon: <IconChart size={17} /> },
    ],
  },
  {
    label: "Directory",
    items: [
      { to: "/platform/facilities", label: "Facilities", icon: <IconHospital size={17} /> },
      { to: "/platform/providers", label: "Doctors", icon: <IconStethoscope size={17} /> },
      { to: "/platform/insurers", label: "Insurers", icon: <IconShield size={17} /> },
    ],
  },
  {
    label: "Governance",
    items: [
      { to: "/platform/verification", label: "Verification", icon: <IconShieldCheck size={17} /> },
      { to: "/platform/access", label: "Access", icon: <IconAlert size={17} /> },
      { to: "/platform/triage", label: "Care Guide", icon: <IconHeart size={17} /> },
      { to: "/platform/settings", label: "Settings", icon: <IconInfo size={17} /> },
    ],
  },
]

export function PlatformRoutes() {
  const { session } = useAuth()
  const who = session.state === "signed_in" ? session.session.display_name : ""

  return (
    <DashboardShell title="Platform" subtitle={who} sections={SECTIONS}>
      <Routes>
        <Route path="/" element={<Overview />} />
        <Route path="/activity" element={<PlatformActivity />} />
        <Route path="/facilities" element={<PlatformFacilities />} />
        <Route path="/providers" element={<PlatformProviders />} />
        <Route path="/verification" element={<Verification />} />
        <Route path="/access" element={<PlatformAccess />} />
        <Route path="/insurers" element={<PlatformInsurers />} />
        <Route path="/settings" element={<PlatformSettings />} />
        <Route path="/triage" element={<TriageMonitor />} />
        <Route path="*" element={<Navigate to="/platform" replace />} />
      </Routes>
    </DashboardShell>
  )
}
