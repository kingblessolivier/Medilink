import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { api } from "../api/client"
import { Chip, EmptyState, ErrorState, TableSkeleton } from "../ui"
import { IconStethoscope } from "../ui/icons"

/**
 * Every doctor listed on the platform.
 *
 * Read-only, like the facility list. Verification happens on its own screen,
 * where a note explaining what was checked is required; a one-click approve
 * from a directory row would be exactly the rubber stamp that screen exists
 * to prevent.
 *
 * A doctor with no facility placement is listed and unreachable - patients
 * can find the name and cannot book with it. Flagged for the same reason a
 * facility with no staff is.
 */
export function PlatformProviders() {
  const [unverifiedOnly, setUnverifiedOnly] = useState(false)

  const query = useQuery({
    queryKey: ["admin", "providers"],
    queryFn: api.adminProviders,
    staleTime: 60_000,
  })

  const all = query.data?.results ?? []
  const rows = unverifiedOnly ? all.filter((p) => !p.verified) : all
  const unplaced = all.filter((p) => p.facilities.length === 0).length

  return (
    <div className="mx-auto w-full max-w-6xl">
      <h1 className="text-h2">Doctors</h1>
      <p className="mt-1 text-small text-ink-muted">
        Everyone listed to patients. Verification is on its own screen.
      </p>

      <label className="mt-5 flex min-h-touch items-center gap-2 text-small">
        <input
          type="checkbox"
          className="ml-checkbox"
          checked={unverifiedOnly}
          onChange={(e) => setUnverifiedOnly(e.target.checked)}
        />
        Show only unverified
      </label>

      <div className="mt-4">
        {query.isLoading && <TableSkeleton rows={6} />}

        {query.isError && (
          <ErrorState
            title="Could not load the doctor list."
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

        {query.isSuccess && rows.length === 0 && (
          <EmptyState
            icon={<IconStethoscope size={20} />}
            title={
              unverifiedOnly
                ? "Every listed doctor is verified."
                : "No doctors listed yet."
            }
          />
        )}

        {rows.length > 0 && (
          <div className="ml-scroll-x rounded-xl border border-line bg-surface">
            <table className="ml-table">
              <thead>
                <tr>
                  <th scope="col">Name</th>
                  <th scope="col">Specialties</th>
                  <th scope="col">Practises at</th>
                  <th scope="col">Status</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((p) => (
                  <tr key={p.id}>
                    <td className="font-medium">{p.full_name}</td>
                    <td className="text-ink-muted">
                      {p.specialties.length > 0
                        ? p.specialties.join(" \u00b7 ")
                        : "\u2014"}
                    </td>
                    <td className="text-ink-muted">
                      {p.facilities.length > 0 ? (
                        p.facilities.join(", ")
                      ) : (
                        // Listed and unreachable: a patient can find the name
                        // and cannot book with it.
                        <Chip tone="warning">No facility</Chip>
                      )}
                    </td>
                    <td>
                      {p.verified ? (
                        <Chip tone="success">Verified</Chip>
                      ) : (
                        <Chip tone="unknown">Not verified</Chip>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {unplaced > 0 && !unverifiedOnly && (
          <p className="mt-3 text-caption text-ink-subtle">
            {unplaced} {unplaced === 1 ? "doctor is" : "doctors are"} listed
            without a facility, so patients cannot book with them.
          </p>
        )}
      </div>
    </div>
  )
}
