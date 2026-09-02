import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { api } from "../api/client"
import { Button, Chip, EmptyState, ErrorState, Field, TableSkeleton, TextInput } from "../ui"

/**
 * Find somebody this facility has seen before.
 *
 * The question reception actually has is narrow: *is this person already
 * checked in, or do I need to add them?* Everything on the row answers that,
 * and nothing else is here - this is deliberately not a patient record
 * viewer.
 *
 * Three constraints, all enforced server-side and none of them cosmetic:
 *
 * - **Scoped to this facility's own patients.** Somebody who has only ever
 *   attended another clinic does not appear. That is the breach docs/08
 *   exists to prevent.
 * - **Every search is written to the access log.** A search that returns a
 *   patient is a read of a patient record.
 * - **Throttled.** Without a limit this is an oracle for testing whether a
 *   number is registered.
 *
 * The phone is masked, exactly as the queue board masks it: this screen is
 * read across a reception desk like any other.
 */

const MIN_QUERY = 3

export function WorkspacePatients() {
  const [term, setTerm] = useState("")
  const [submitted, setSubmitted] = useState("")

  const query = useQuery({
    queryKey: ["staff", "patients", submitted],
    queryFn: () => api.patientLookup(submitted),
    enabled: submitted.length >= MIN_QUERY,
    // Not cached for long: "are they in the queue now" goes stale in minutes,
    // and a stale yes sends a receptionist looking for a ticket that is gone.
    staleTime: 30_000,
  })

  const results = query.data?.results ?? []
  const tooShort = term.length > 0 && term.length < MIN_QUERY

  return (
    <div>
      <div className="ml-section-head">
        <div>
          <h1 className="text-h2">Find a patient</h1>
          <p className="mt-1 text-body text-n700">
            Patients this facility has seen before. Searching is recorded.
          </p>
        </div>
      </div>

      <form
        className="mb-5 max-w-md"
        onSubmit={(e) => {
          e.preventDefault()
          setSubmitted(term.trim())
        }}
      >
        <Field
          label="Phone number or name"
          hint={`At least ${MIN_QUERY} characters.`}
          error={tooShort ? "Keep typing — three characters or more." : undefined}
        >
          {(id, describedBy) => (
            <TextInput
              id={id}
              aria-describedby={describedBy}
              placeholder="0788… or a name"
              autoComplete="off"
              value={term}
              onChange={(e) => setTerm(e.target.value)}
            />
          )}
        </Field>
        <div className="mt-3">
          <Button
            variant="primary"
            size="sm"
            loading={query.isFetching}
            disabled={term.trim().length < MIN_QUERY}
          >
            Search
          </Button>
        </div>
      </form>

      {query.isFetching && <TableSkeleton rows={3} />}

      {query.isError && (
        <ErrorState
          title="Could not search."
          body="If this keeps happening, wait a moment and try again."
          action={
            <Button size="sm" onClick={() => query.refetch()}>
              Try again
            </Button>
          }
        />
      )}

      {!query.isFetching && submitted.length >= MIN_QUERY && results.length === 0 && (
        <EmptyState
          title="Nobody here matches that"
          body="This searches only patients this facility has seen. Somebody attending for the first time will not appear — check them in as a new patient."
        />
      )}

      {results.length > 0 && (
        <div className="ml-scroller">
          <table className="ml-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Phone</th>
                <th>Visits here</th>
                <th>Last seen</th>
                <th>Right now</th>
              </tr>
            </thead>
            <tbody>
              {results.map((person) => (
                <tr key={person.id}>
                  <td>{person.display_name || <span className="text-n600">No name on file</span>}</td>
                  <td className="tabular-nums">{person.phone}</td>
                  <td className="tabular-nums">{person.visits_here}</td>
                  <td className="tabular-nums">
                    {person.last_seen ?? <span className="text-n600">—</span>}
                  </td>
                  <td>
                    {person.in_queue_now ? (
                      <Chip tone="success">In the queue · {person.ticket_code}</Chip>
                    ) : (
                      <span className="text-body text-n700">Not checked in</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
