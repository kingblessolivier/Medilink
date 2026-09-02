import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api, ApiRequestError } from "../api/client"
import { Button, Chip, ErrorState, Notice, Select, TableSkeleton } from "../ui"
import type { CoverageLevel, InsurerWithCoverage } from "../api/types"

/**
 * What this facility accepts, maintained by this facility.
 *
 * The screen used to be read-only, on the reasoning that a facility editing
 * its own coverage would be publishing an unchecked claim. That was reversed
 * deliberately: the facility runs the counter that takes the card, so nobody
 * is better placed to say what it accepts, and routing every change through
 * MediLink is the bottleneck that stops a second pilot site.
 *
 * Rule 6 of docs/11 section 7 is unaffected and still holds. It governs the
 * WORDS - "Accepts Mutuelle", never "You are covered" - not who edits them.
 * What is stored is facility-declared acceptance, not a patient's
 * eligibility, and the labels below say so.
 *
 * `unknown` is offered as a coverage value on purpose. A facility that has
 * not checked whether Mutuelle covers dentistry should be able to say that,
 * and it is stored unconfirmed so a patient reads "Not confirmed" rather than
 * a guess dressed up as an answer.
 */

const COVERAGE_LABEL: Record<CoverageLevel, string> = {
  full: "Accepted",
  partial: "Partly accepted",
  not_covered: "Not accepted",
  unknown: "Not confirmed",
}

const COVERAGE_TONE: Record<CoverageLevel, "success" | "warning" | "neutral"> = {
  full: "success",
  partial: "warning",
  not_covered: "neutral",
  unknown: "neutral",
}

export function WorkspaceInsurance({ canManage }: { canManage: boolean }) {
  const client = useQueryClient()

  const query = useQuery({
    queryKey: ["staff", "insurance"],
    queryFn: api.facilityInsurance,
    staleTime: 60_000,
  })

  const invalidate = () =>
    client.invalidateQueries({ queryKey: ["staff", "insurance"] })

  const accept = useMutation({
    mutationFn: ({ code, accepted }: { code: string; accepted: boolean }) =>
      api.setInsurerAccepted(code, { accepted }),
    onSuccess: invalidate,
  })

  const cover = useMutation({
    mutationFn: (args: { code: string; service: string; coverage: CoverageLevel }) =>
      api.setServiceCoverage(args.code, args.service, { coverage: args.coverage }),
    onSuccess: invalidate,
  })

  const failure = accept.error ?? cover.error
  const rows = query.data?.results ?? []
  const accepted = rows.filter((r) => r.accepted)

  return (
    <div>
      <div className="ml-section-head">
        <div>
          <h1 className="text-h2">Insurance</h1>
          <p className="mt-1 text-body text-n700">
            What this facility accepts at its counter. Patients see this as
            &ldquo;Accepts Mutuelle&rdquo; &mdash; never as confirmation that
            they personally are covered.
          </p>
        </div>
      </div>

      {failure && (
        <div className="mb-4">
          <Notice tone="warning">
            {failure instanceof ApiRequestError
              ? failure.message
              : "Could not save that. Try again."}
          </Notice>
        </div>
      )}

      {accepted.length === 0 && !query.isLoading && (
        <div className="mb-4">
          <Notice tone="warning">
            This facility accepts no insurance, so it will not appear when a
            patient filters by their insurer.
          </Notice>
        </div>
      )}

      {query.isLoading && <TableSkeleton rows={4} />}
      {query.isError && (
        <ErrorState
          title="Could not load insurance."
          action={
            <Button size="sm" onClick={() => query.refetch()}>
              Try again
            </Button>
          }
        />
      )}

      <div className="space-y-4">
        {rows.map((insurer) => (
          <InsurerBlock
            key={insurer.code}
            insurer={insurer}
            canManage={canManage}
            busy={accept.isPending || cover.isPending}
            onToggle={() =>
              accept.mutate({
                code: insurer.code,
                accepted: !insurer.accepted,
              })
            }
            onCoverage={(service, coverage) =>
              cover.mutate({ code: insurer.code, service, coverage })
            }
          />
        ))}
      </div>
    </div>
  )
}

function InsurerBlock({
  insurer,
  canManage,
  busy,
  onToggle,
  onCoverage,
}: {
  insurer: InsurerWithCoverage
  canManage: boolean
  busy: boolean
  onToggle: () => void
  onCoverage: (service: string, coverage: CoverageLevel) => void
}) {
  return (
    <section className="rounded-md border border-n200 bg-white">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-n200 px-4 py-3">
        <div className="min-w-0">
          <h2 className="text-h3">{insurer.name}</h2>
          <p className="mt-0.5 text-body text-n700">
            {insurer.accepted
              ? "Accepted at this facility"
              : "Not accepted here"}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Chip tone={insurer.accepted ? "success" : "neutral"}>
            {insurer.accepted ? "Accepted" : "Not accepted"}
          </Chip>
          {canManage && (
            <Button
              size="sm"
              variant={insurer.accepted ? "secondary" : "primary"}
              disabled={busy}
              onClick={onToggle}
            >
              {insurer.accepted ? "Stop accepting" : "Accept"}
            </Button>
          )}
        </div>
      </header>

      {/* Per-service coverage only means something for an insurer the
          facility takes at all. Hidden rather than disabled: a table of greyed
          selects invites somebody to fight it. */}
      {insurer.accepted && (
        <div className="ml-scroller">
          <table className="ml-table">
            <thead>
              <tr>
                <th>Service</th>
                <th>Covered here</th>
                {canManage && <th aria-label="Change" />}
              </tr>
            </thead>
            <tbody>
              {insurer.services.map((service) => (
                <tr key={service.code}>
                  <td>{service.name_en}</td>
                  <td>
                    <Chip tone={COVERAGE_TONE[service.coverage]}>
                      {COVERAGE_LABEL[service.coverage]}
                    </Chip>
                  </td>
                  {canManage && (
                    <td>
                      <Select
                        aria-label={`${insurer.name} coverage for ${service.name_en}`}
                        value={service.coverage}
                        disabled={busy}
                        onChange={(e) =>
                          onCoverage(
                            service.code,
                            e.target.value as CoverageLevel,
                          )
                        }
                      >
                        {(
                          ["full", "partial", "not_covered", "unknown"] as const
                        ).map((level) => (
                          <option key={level} value={level}>
                            {COVERAGE_LABEL[level]}
                          </option>
                        ))}
                      </Select>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {insurer.accepted && insurer.services.length === 0 && (
        <p className="px-4 py-3 text-body text-n700">
          Add services to this facility before setting what this insurer
          covers.
        </p>
      )}
    </section>
  )
}
