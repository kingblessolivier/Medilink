import { useQuery } from "@tanstack/react-query"
import { api, type Me, type ServiceBrief } from "../api/client"
import { Chip, EmptyState, ErrorState, Notice, TableSkeleton } from "../ui"

/**
 * How this facility appears to a patient searching for care.
 *
 * The point of the screen is the mirror: a facility manager should be able to
 * see, in one place, what a patient sees - including the gaps. An insurer with
 * unknown coverage shows as unknown here, in the same quiet grey, rather than
 * being tidied away. That is what prompts somebody to go and confirm it.
 *
 * Read-only for the same reason as Doctors: a facility that could edit its own
 * coverage claims would be publishing "you are covered" without anyone
 * checking. See docs/11 section 7.
 */

/**
 * Keys match apps.insurance.models.FacilityServiceInsurer.Coverage exactly.
 *
 * The wording is the "Accepts Mutuelle" rule from docs/11 section 7: MediLink
 * states what the FACILITY accepts, never what a patient is covered for. A
 * facility manager reading this screen sees the same careful phrasing their
 * patients do, which is the point of the screen.
 */
const COVERAGE_LABEL: Record<string, string> = {
  full: "Accepted",
  partial: "Partly accepted",
  not_covered: "Not accepted",
  unknown: "Not confirmed",
}

const COVERAGE_TONE: Record<string, "success" | "warning" | "neutral"> = {
  full: "success",
  partial: "warning",
  not_covered: "neutral",
  unknown: "neutral",
}

export function Services({ me }: { me: Me }) {
  const query = useQuery({
    queryKey: ["facility", me.facility.slug],
    queryFn: () => api.facility(me.facility.slug),
    staleTime: 10 * 60_000,
  })

  const facility = query.data
  const services = facility?.services ?? []

  return (
    <div className="mx-auto w-full max-w-4xl">
      <h1 className="text-h2">Services</h1>
      <p className="mt-1 text-small text-ink-muted">
        What patients find when they search for care near you.
      </p>

      {query.isLoading && (
        <div className="mt-6">
          <TableSkeleton rows={4} />
        </div>
      )}

      {query.isError && (
        <div className="mt-6">
          <ErrorState
            title="Could not load your facility page."
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

      {facility && (
        <>
          {/* ------------------------------------------------ open / shut */}
          <div className="mt-5 flex flex-wrap items-center gap-2">
            {facility.is_open ? (
              <Chip tone="success">Open now</Chip>
            ) : (
              <Chip tone="neutral">Closed now</Chip>
            )}
            {facility.verified_at ? (
              <Chip tone="success">Verified facility</Chip>
            ) : (
              <Chip tone="neutral">Not yet verified</Chip>
            )}
            {!me.facility.reports_queue && (
              <Chip tone="neutral">Wait times not published</Chip>
            )}
          </div>

          {/* -------------------------------------------------- insurers */}
          <section className="mt-8">
            <h2 className="ml-label mb-3">Insurers listed</h2>
            {facility.insurers.length === 0 ? (
              <p className="text-body text-ink-muted">
                No insurers recorded. Patients filtering by insurance will not
                find you.
              </p>
            ) : (
              <ul className="flex flex-wrap gap-2">
                {facility.insurers.map((insurer) => (
                  <li key={insurer.code}>
                    <Chip tone="neutral">{insurer.name}</Chip>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {/* -------------------------------------------------- services */}
          <section className="mt-8">
            <h2 className="ml-label mb-3">Services offered</h2>

            {services.length === 0 ? (
              <EmptyState
                title="No services listed."
                body="Patients cannot find or book with you until at least one service is recorded."
              />
            ) : (
              <ul className="space-y-3">
                {services.map((service) => (
                  <ServiceRow key={service.code} service={service} />
                ))}
              </ul>
            )}
          </section>

          <div className="mt-8">
            <Notice tone="info">
              Services and insurance are maintained by MediLink so that no
              facility can publish cover a patient does not have. To add or
              correct one, contact support.
            </Notice>
          </div>
        </>
      )}
    </div>
  )
}

function ServiceRow({ service }: { service: ServiceBrief }) {
  return (
    <li className="rounded-lg border border-line bg-surface p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="text-body font-medium">{service.name_en}</span>
        <WaitLabel wait={service.wait} />
      </div>

      <p className="mt-0.5 text-small text-ink-muted">{service.name_rw}</p>

      {service.coverage.length > 0 && (
        <ul className="mt-3 flex flex-wrap gap-2">
          {service.coverage.map((row) => (
            <li key={row.insurer}>
              <Chip tone={COVERAGE_TONE[row.coverage] ?? "neutral"}>
                {/* A value this build does not know falls back to the honest
                    one, never to the raw enum string. */}
                {row.insurer_name}:{" "}
                {COVERAGE_LABEL[row.coverage] ?? COVERAGE_LABEL.unknown}
              </Chip>
            </li>
          ))}
        </ul>
      )}
    </li>
  )
}

function WaitLabel({ wait }: { wait: ServiceBrief["wait"] }) {
  // Four states, and only one of them is a number. A facility looking at
  // "Not enough data" is looking at the reason patients are not seeing a wait
  // time - which is the useful thing to show them.
  if (wait.status === "available" && wait.minutes !== null) {
    return (
      <span className="tabular-nums text-small text-ink-muted">
        About {wait.minutes} min wait
      </span>
    )
  }
  return (
    <span className="text-small text-ink-subtle">
      {wait.status === "closed"
        ? "Closed"
        : wait.status === "insufficient_data"
          ? "Not enough data to publish a wait"
          : "Wait not reported"}
    </span>
  )
}
