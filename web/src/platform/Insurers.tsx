import { useState } from "react"
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
 * The insurers every facility chooses from.
 *
 * They were a fixture file, so adding one was a deploy. There are a handful in
 * Rwanda and the list changes rarely - but "rarely" is not "never", and a
 * scheme launching mid-year should not wait for a release.
 *
 * The facilities column is the number to look at before touching anything: it
 * is how many facilities' acceptance records point at this row, and therefore
 * how many patients a mistake would misdirect.
 *
 * There is no delete. An insurer with facilities behind it cannot be removed
 * without silently dropping their acceptance, and a facility that stops
 * appearing under Mutuelle because somebody tidied a list is a patient sent to
 * the wrong place. Hiding it from patients is `is_public`.
 */
export function PlatformInsurers() {
  const client = useQueryClient()
  const [draft, setDraft] = useState({ code: "", name: "" })

  const query = useQuery({
    queryKey: ["platform", "insurers"],
    queryFn: api.adminInsurers,
    staleTime: 60_000,
  })

  const invalidate = () =>
    client.invalidateQueries({ queryKey: ["platform", "insurers"] })

  const add = useMutation({
    mutationFn: () => api.createInsurer(draft),
    onSuccess: () => {
      setDraft({ code: "", name: "" })
      invalidate()
    },
  })

  const update = useMutation({
    mutationFn: (args: { code: string; is_public: boolean }) =>
      api.updateInsurer(args.code, { is_public: args.is_public }),
    onSuccess: invalidate,
  })

  const failure = add.error ?? update.error
  const rows = query.data?.results ?? []

  return (
    <div>
      <div className="ml-section-head">
        <div>
          <h1 className="text-h2">Insurers</h1>
          <p className="mt-1 text-body text-n700">
            The list every facility chooses from, and every patient filters by.
          </p>
        </div>
      </div>

      {failure && (
        <div className="mb-4">
          <Notice tone="warning">
            {failure instanceof ApiRequestError
              ? failure.message
              : "Could not save. Try again."}
          </Notice>
        </div>
      )}

      <form
        className="mb-6 flex flex-wrap items-end gap-3 rounded-md border border-n200 bg-white p-4"
        onSubmit={(e) => {
          e.preventDefault()
          add.mutate()
        }}
      >
        <Field label="Code" hint="Lowercase, no spaces. Cannot be changed later.">
          {(id) => (
            <TextInput
              id={id}
              className="w-40"
              value={draft.code}
              autoCapitalize="none"
              spellCheck={false}
              onChange={(e) =>
                setDraft({ ...draft, code: e.target.value.toLowerCase() })
              }
            />
          )}
        </Field>
        <Field label="Name" hint="As a patient would recognise it.">
          {(id) => (
            <TextInput
              id={id}
              className="w-64"
              value={draft.name}
              onChange={(e) => setDraft({ ...draft, name: e.target.value })}
            />
          )}
        </Field>
        <Button
          variant="primary"
          size="sm"
          loading={add.isPending}
          disabled={!draft.code.trim() || !draft.name.trim()}
        >
          Add insurer
        </Button>
      </form>

      {query.isLoading && <TableSkeleton rows={4} />}
      {query.isError && (
        <ErrorState
          title="Could not load insurers."
          action={
            <Button size="sm" onClick={() => query.refetch()}>
              Try again
            </Button>
          }
        />
      )}

      {rows.length > 0 && (
        <div className="ml-scroller">
          <table className="ml-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Code</th>
                <th>Facilities accepting</th>
                <th>Shown to patients</th>
                <th aria-label="Change" />
              </tr>
            </thead>
            <tbody>
              {rows.map((insurer) => (
                <tr key={insurer.code}>
                  <td>{insurer.name}</td>
                  <td className="font-mono text-body text-n700">
                    {insurer.code}
                  </td>
                  <td className="tabular-nums">{insurer.facilities}</td>
                  <td>
                    <Chip tone={insurer.is_public ? "success" : "neutral"}>
                      {insurer.is_public ? "Yes" : "Hidden"}
                    </Chip>
                  </td>
                  <td>
                    <Button
                      size="sm"
                      variant="secondary"
                      disabled={update.isPending}
                      onClick={() =>
                        update.mutate({
                          code: insurer.code,
                          is_public: !insurer.is_public,
                        })
                      }
                    >
                      {insurer.is_public ? "Hide" : "Show"}
                    </Button>
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
