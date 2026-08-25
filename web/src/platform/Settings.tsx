import { useEffect, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api, ApiRequestError } from "../api/client"
import {
  Button,
  Chip,
  ErrorState,
  Field,
  Notice,
  TableSkeleton,
  TextInput,
} from "../ui"

/**
 * Platform configuration.
 *
 * The interesting part of this screen is the second half, which shows values
 * an administrator deliberately CANNOT change.
 *
 * `MIN_SERVICE_TIME_SAMPLES` is the honesty rule made executable - the gate
 * that stops a wait estimate being published from too few visits. A field on
 * this form would be an invitation to lower it the first time a facility
 * complains that its waits show as unavailable, and the entire value of the
 * rule is that it cannot be argued down in the moment.
 *
 * It is shown, though, because an administrator asking "why does this
 * facility have no wait time" needs to see that the gate is 20. Hiding it
 * would make the system feel arbitrary rather than principled.
 *
 * The privacy notice version and the triage sign-off are here for the same
 * reason and stay fixed for their own: one is only meaningful next to the
 * notice text that ships with the code, and the other is evidence that a
 * named clinician approved a specific protocol.
 */
export function PlatformSettings() {
  const client = useQueryClient()
  const [radius, setRadius] = useState("")
  const [saved, setSaved] = useState(false)

  const query = useQuery({
    queryKey: ["platform", "settings"],
    queryFn: api.platformSettings,
    staleTime: 60_000,
  })

  useEffect(() => {
    if (query.data) setRadius(String(query.data.default_search_radius_m))
  }, [query.data])

  const save = useMutation({
    mutationFn: () =>
      api.updatePlatformSettings({
        default_search_radius_m: Number(radius),
      }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["platform", "settings"] })
      setSaved(true)
      setTimeout(() => setSaved(false), 2500)
    },
  })

  const data = query.data

  return (
    <div>
      <div className="ml-section-head">
        <div>
          <h1 className="text-h2">Platform settings</h1>
          <p className="mt-1 text-small text-ink-muted">
            Configuration that applies across every facility.
          </p>
        </div>
        {saved && <Chip tone="success">Saved.</Chip>}
      </div>

      {save.error && (
        <div className="mb-4">
          <Notice tone="warning">
            {save.error instanceof ApiRequestError
              ? save.error.message
              : "Could not save. Try again."}
          </Notice>
        </div>
      )}

      {query.isLoading && <TableSkeleton rows={3} />}
      {query.isError && (
        <ErrorState
          title="Could not load settings."
          action={
            <Button size="sm" onClick={() => query.refetch()}>
              Try again
            </Button>
          }
        />
      )}

      {data && (
        <div className="space-y-8">
          <section className="max-w-md">
            <h2 className="text-h3 mb-3">Search</h2>
            <form
              onSubmit={(e) => {
                e.preventDefault()
                save.mutate()
              }}
            >
              <Field
                label="Starting search radius (metres)"
                hint="Where a nearby search begins before it widens on its own. Kigali is dense; a rural district is not."
              >
                {(id, describedBy) => (
                  <TextInput
                    id={id}
                    aria-describedby={describedBy}
                    inputMode="numeric"
                    value={radius}
                    onChange={(e) =>
                      setRadius(e.target.value.replace(/\D/g, ""))
                    }
                  />
                )}
              </Field>
              <div className="mt-3">
                <Button variant="primary" size="sm" loading={save.isPending}>
                  Save
                </Button>
              </div>
            </form>
          </section>

          {/* The half that matters. */}
          <section>
            <h2 className="text-h3">Fixed at deploy</h2>
            <p className="mt-1 max-w-prose text-small text-ink-muted">
              These are shown so you can answer questions about them. They are
              deliberately not editable here — each is a decision that should
              take a release and a review, not a form.
            </p>

            <dl className="mt-3 divide-y divide-line rounded-xl border border-line bg-surface">
              {data.fixed.map((item) => (
                <div key={item.key} className="px-4 py-3">
                  <dt className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-small text-ink">
                      {item.key}
                    </span>
                    <Chip tone="neutral">{item.value}</Chip>
                  </dt>
                  <dd className="mt-1 max-w-prose text-small text-ink-muted">
                    {item.why}
                  </dd>
                </div>
              ))}
            </dl>
          </section>
        </div>
      )}
    </div>
  )
}
