import { useState } from "react"
import { IconShieldCheck } from "../ui/icons"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api, type PendingFacility, type PendingProvider } from "../api/client"
import { Chip, EmptyState, ErrorState, Notice, Skeleton } from "../ui"

/**
 * The verification queue.
 *
 * Verifying is an assertion that a person checked documents, so the note is
 * required and the button stays disabled until one is written. An approval
 * with no record of what was checked is indistinguishable from a mis-click -
 * and this particular mis-click puts a facility in front of patients.
 *
 * There is no "reject" and no "unverify". Rejection is a conversation, not a
 * button, and un-verifying would overwrite the record of who approved it. Both
 * belong in Django admin with its own audit trail, where doing them is
 * deliberate.
 */
export function Verification() {
  const queryClient = useQueryClient()

  const query = useQuery({
    queryKey: ["verification"],
    queryFn: api.verificationQueue,
  })

  const facilities = query.data?.facilities ?? []
  const providers = query.data?.providers ?? []
  const empty = facilities.length === 0 && providers.length === 0

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["verification"] })
    // The overview leads with this backlog, so it goes stale the moment
    // anything here is approved.
    queryClient.invalidateQueries({ queryKey: ["overview"] })
  }

  return (
    <div className="mx-auto w-full max-w-3xl">
      <h1 className="text-h2">Verification</h1>
      <p className="mt-1 text-small text-ink-muted">
        Until a facility is verified, patients cannot find it. Oldest first.
      </p>

      {query.isLoading && (
        <div className="mt-6 space-y-3">
          {Array.from({ length: 3 }, (_, i) => (
            <div key={i} className="rounded-lg border border-line bg-surface p-4">
              <Skeleton className="h-4 w-1/3" />
              <Skeleton className="mt-2 h-3 w-1/4" />
            </div>
          ))}
        </div>
      )}

      {query.isError && (
        <div className="mt-6">
          <ErrorState
            title="Could not load the verification queue."
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

      {query.isSuccess && empty && (
        <div className="mt-6">
          <EmptyState icon={<IconShieldCheck size={20} />}
            title="Nothing waiting."
            body="Every listed facility and doctor has been verified."
          />
        </div>
      )}

      {facilities.length > 0 && (
        <section className="mt-8">
          <h2 className="text-h3 mb-3">
            Facilities ({facilities.length})
          </h2>
          <ul className="space-y-3">
            {facilities.map((facility) => (
              <FacilityRow
                key={facility.id}
                facility={facility}
                onVerified={invalidate}
              />
            ))}
          </ul>
        </section>
      )}

      {providers.length > 0 && (
        <section className="mt-8">
          <h2 className="text-h3 mb-3">Doctors ({providers.length})</h2>
          <ul className="space-y-3">
            {providers.map((provider) => (
              <ProviderRow
                key={provider.id}
                provider={provider}
                onVerified={invalidate}
              />
            ))}
          </ul>
        </section>
      )}

      <div className="mt-8">
        <Notice tone="info">
          Rejecting a listing is a conversation, not a button, and un-verifying
          would overwrite the record of who approved it. Both are done in
          Django admin, deliberately.
        </Notice>
      </div>
    </div>
  )
}

function FacilityRow({
  facility,
  onVerified,
}: {
  facility: PendingFacility
  onVerified: () => void
}) {
  const verify = useMutation({
    mutationFn: (note: string) => api.verifyFacility(facility.id, note),
    onSuccess: onVerified,
  })

  return (
    <Row
      title={facility.name}
      subtitle={`${facility.district} · ${humanise(facility.level)} · ${humanise(facility.ownership)}`}
      detail={facility.phone || undefined}
      placeholder="What did you check? e.g. Licence 2026/114 sighted; coordinates captured on site."
      pending={verify.isPending}
      error={verify.isError ? (verify.error as Error).message : null}
      onVerify={(note) => verify.mutate(note)}
    />
  )
}

function ProviderRow({
  provider,
  onVerified,
}: {
  provider: PendingProvider
  onVerified: () => void
}) {
  const verify = useMutation({
    mutationFn: (note: string) => api.verifyProvider(provider.id, note),
    onSuccess: onVerified,
  })

  return (
    <Row
      title={provider.full_name}
      subtitle={
        provider.specialties.length > 0
          ? provider.specialties.join(" · ")
          : "No specialty recorded"
      }
      placeholder="What did you check? e.g. RMDC registration 4471 confirmed against the register."
      pending={verify.isPending}
      error={verify.isError ? (verify.error as Error).message : null}
      onVerify={(note) => verify.mutate(note)}
    />
  )
}

function Row({
  title,
  subtitle,
  detail,
  placeholder,
  pending,
  error,
  onVerify,
}: {
  title: string
  subtitle: string
  detail?: string
  placeholder: string
  pending: boolean
  error: string | null
  onVerify: (note: string) => void
}) {
  const [note, setNote] = useState("")
  const ready = note.trim().length > 0

  return (
    <li className="rounded-lg border border-line bg-surface p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="text-body font-medium">{title}</span>
        <Chip tone="neutral">Not yet verified</Chip>
      </div>
      <p className="mt-0.5 text-small text-ink-muted">{subtitle}</p>
      {detail && (
        <p className="mt-0.5 text-small tabular-nums text-ink-muted">{detail}</p>
      )}

      <label className="mt-3 block">
        <span className="ml-label block">Verification note</span>
        <textarea
          className="ml-field mt-1 min-h-[4.5rem]"
          placeholder={placeholder}
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
      </label>

      {error && (
        <p className="mt-2 text-small text-danger" role="alert">
          {error}
        </p>
      )}

      <div className="mt-3 flex items-center gap-3">
        <button
          className="ml-btn-primary ml-btn-sm"
          // Disabled until a note exists: the note IS the verification, and a
          // one-click approve would make this a rubber stamp.
          disabled={!ready || pending}
          onClick={() => onVerify(note.trim())}
        >
          {pending ? "Verifying..." : "Verify"}
        </button>
        {!ready && (
          <span className="text-caption text-ink-subtle">
            Write what you checked to enable this.
          </span>
        )}
      </div>
    </li>
  )
}

function humanise(code: string) {
  return code.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase())
}
