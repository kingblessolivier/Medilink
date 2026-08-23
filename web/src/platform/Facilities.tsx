import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { api, type AdminFacility } from "../api/client"
import { Chip, ErrorState, Notice, TableSkeleton } from "../ui"
import { IconAlert, IconHospital } from "../ui/icons"

/**
 * Every facility on the platform, and specifically the ones that look fine
 * and are not.
 *
 * A facility can be verified, listed, and findable by patients while being
 * completely unable to do anything - no staff account means nobody can check
 * a patient in, and `reports_queue = false` means it publishes no wait times.
 * Neither is visible from the patient side. Both are flagged here, because
 * this is the only screen where anybody would notice.
 */

const LEVEL: Record<string, string> = {
  health_post: "Health post",
  health_centre: "Health centre",
  district_hospital: "District hospital",
  referral_hospital: "Referral hospital",
  clinic: "Clinic",
  pharmacy: "Pharmacy",
}

type Filter = "all" | "needs_attention" | "unverified"

export function PlatformFacilities() {
  const [filter, setFilter] = useState<Filter>("all")

  const query = useQuery({
    queryKey: ["admin", "facilities"],
    queryFn: api.adminFacilities,
    staleTime: 60_000,
  })

  const all = query.data?.results ?? []
  const attention = all.filter(needsAttention)
  const rows =
    filter === "needs_attention"
      ? attention
      : filter === "unverified"
        ? all.filter((f) => !f.verified)
        : all

  return (
    <div className="mx-auto w-full max-w-6xl">
      <h1 className="text-h2">Facilities</h1>
      <p className="mt-1 text-small text-ink-muted">
        Every facility on the platform, verified or not.
      </p>

      {attention.length > 0 && (
        <div className="mt-5">
          <Notice tone="warning">
            {attention.length} verified{" "}
            {attention.length === 1 ? "facility is" : "facilities are"} listed
            to patients but cannot check anybody in, or publish no wait times.
          </Notice>
        </div>
      )}

      <div className="mt-5 flex flex-wrap gap-1" role="group">
        {(
          [
            ["all", `All ${all.length}`],
            ["needs_attention", `Needs attention ${attention.length}`],
            ["unverified", `Unverified ${all.filter((f) => !f.verified).length}`],
          ] as [Filter, string][]
        ).map(([value, label]) => (
          <button
            key={value}
            aria-pressed={filter === value}
            className={
              filter === value
                ? "ml-btn-primary ml-btn-sm"
                : "ml-btn-secondary ml-btn-sm"
            }
            onClick={() => setFilter(value)}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="mt-4">
        {query.isLoading && <TableSkeleton rows={6} />}

        {query.isError && (
          <ErrorState
            title="Could not load the facility list."
            action={
              <button
                className="ml-btn-secondary ml-btn-sm"
                onClick={() => query.refetch()}
              >
                Try again
              </button>
            }
          />
        )}

        {rows.length > 0 && (
          <div className="overflow-x-auto rounded-xl border border-line bg-surface">
            <table className="ml-table">
              <thead>
                <tr>
                  <th scope="col">Facility</th>
                  <th scope="col">District</th>
                  <th scope="col">Level</th>
                  <th scope="col">Staff</th>
                  <th scope="col">Services</th>
                  <th scope="col">Status</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((f) => (
                  <Row key={f.id} facility={f} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

/** Listed to patients, and unable to serve them. */
function needsAttention(f: AdminFacility): boolean {
  return f.verified && (f.staff_count === 0 || f.service_count === 0)
}

function Row({ facility: f }: { facility: AdminFacility }) {
  return (
    <tr>
      <td>
        <span className="flex items-center gap-2.5">
          <span className="ml-icon-plate h-8 w-8 shrink-0 bg-surface-sunken text-ink-muted">
            <IconHospital size={16} />
          </span>
          <span className="min-w-0">
            <span className="block truncate font-medium">{f.name}</span>
            <span className="block truncate text-caption text-ink-subtle">
              {f.ownership === "public" ? "Public" : "Private"}
            </span>
          </span>
        </span>
      </td>
      <td className="text-ink-muted">{f.district}</td>
      <td className="text-ink-muted">{LEVEL[f.level] ?? f.level}</td>
      <td className="tabular-nums">
        {f.staff_count === 0 ? (
          <Chip tone="warning">
            <IconAlert size={13} />
            None
          </Chip>
        ) : (
          f.staff_count
        )}
      </td>
      <td className="tabular-nums">
        {f.service_count === 0 ? (
          <Chip tone="warning">None</Chip>
        ) : (
          f.service_count
        )}
      </td>
      <td>
        <span className="flex flex-wrap gap-1.5">
          {f.verified ? (
            <Chip tone="success">Verified</Chip>
          ) : (
            <Chip tone="unknown">Not verified</Chip>
          )}
          {/* Not an error - most facilities will never report a queue. It is
              stated because it explains why a facility shows no wait time. */}
          {f.reports_queue && <Chip tone="neutral">Reports queue</Chip>}
        </span>
      </td>
    </tr>
  )
}
