import { useQuery } from "@tanstack/react-query"
import { api, type Me } from "../api/client"
import { Chip, EmptyState, ErrorState, Notice, TableSkeleton } from "../ui"

/**
 * The doctors patients see listed under this facility.
 *
 * Read-only, and deliberately so. Editing a clinician's specialties or
 * verification status from a reception login would let a facility publish
 * qualifications nobody checked - the exact thing docs/11 section 7 forbids.
 * Changes go through MediLink, against documents.
 *
 * It reads the PUBLIC endpoint on purpose: this screen answers "how do we
 * appear to patients?", so it should show what patients are shown.
 */
export function Doctors({ me }: { me: Me }) {
  const query = useQuery({
    queryKey: ["facility-providers", me.facility.slug],
    queryFn: () => api.facilityProviders(me.facility.slug),
    staleTime: 10 * 60_000,
  })

  const rows = query.data?.results ?? []

  return (
    <div className="mx-auto w-full max-w-4xl">
      <h1 className="text-h2">Doctors</h1>
      <p className="mt-1 text-small text-ink-muted">
        As patients see them on your facility page.
      </p>

      {query.isLoading && (
        <div className="mt-6">
          <TableSkeleton rows={3} />
        </div>
      )}

      {query.isError && (
        <div className="mt-6">
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
        </div>
      )}

      {query.isSuccess && rows.length === 0 && (
        <div className="mt-6">
          <EmptyState
            title="No doctors listed for this facility yet."
            body="Patients still see your services and can still book. Contact MediLink to add clinicians."
          />
        </div>
      )}

      {rows.length > 0 && (
        <ul className="mt-6 space-y-2">
          {rows.map((provider) => (
            <li
              key={provider.slug}
              className="flex items-start gap-3 rounded-lg border border-line bg-surface p-4"
            >
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-surface-sunken text-small font-medium text-ink-muted">
                {provider.initials}
              </span>

              <span className="min-w-0 flex-1">
                <span className="flex flex-wrap items-center gap-2">
                  <span className="text-body font-medium">
                    {provider.display_name}
                  </span>
                  {provider.verified ? (
                    <Chip tone="success">Verified</Chip>
                  ) : (
                    // Not an error state - just not checked yet. The quietest
                    // thing on the row.
                    <Chip tone="neutral">Not yet verified</Chip>
                  )}
                </span>

                <span className="mt-1 block text-small text-ink-muted">
                  {/* .join() on the old string[] compiled fine after the API
                      started sending objects, and would have rendered
                      "[object Object]" at a facility manager. */}
                  {provider.specialties.length > 0
                    ? provider.specialties
                        .map((s) => s.name_en)
                        .join(" · ")
                    : "No specialty recorded"}
                </span>

                {provider.languages.length > 0 && (
                  <span className="mt-0.5 block text-caption text-ink-subtle">
                    Speaks {provider.languages.join(", ")}
                  </span>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-6">
        <Notice tone="info">
          Names, specialties and verification are maintained by MediLink against
          submitted documents. To correct an entry, contact support rather than
          changing it here.
        </Notice>
      </div>
    </div>
  )
}
