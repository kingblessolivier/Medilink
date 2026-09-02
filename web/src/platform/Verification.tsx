import { useState, type ReactNode } from "react"
import {
  IconHospital,
  IconShieldCheck,
  IconStethoscope,
} from "../ui/icons"
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
    <div className="mx-auto w-full max-w-5xl">
      <h1 className="text-h2">Verification</h1>
      <p className="mt-1 text-body text-n700">
        Until a facility is verified, patients cannot find it. Oldest first.
      </p>

      {query.isLoading && (
        <div className="mt-6 space-y-3">
          {Array.from({ length: 3 }, (_, i) => (
            <div key={i} className="rounded-md border border-n200 bg-white p-4">
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
      icon={<IconHospital size={18} />}
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
      icon={<IconStethoscope size={18} />}
      placeholder="What did you check? e.g. RMDC registration 4471 confirmed against the register."
      pending={verify.isPending}
      error={verify.isError ? (verify.error as Error).message : null}
      onVerify={(note) => verify.mutate(note)}
    />
  )
}

/**
 * One item awaiting verification.
 *
 * Collapsed until you open it. Twelve doctors used to mean twelve textareas
 * open at once - a 3600px page of mostly empty input boxes, when the actual
 * workflow is: scan the list, pick one, check the register, write what you
 * checked, approve. Only one is ever being worked on.
 *
 * Opening is what commits you to reading it, which is the point: this is the
 * step that puts a facility in front of patients, and a form that is already
 * open invites a rubber stamp.
 */
function Row({
  title,
  subtitle,
  detail,
  placeholder,
  pending,
  error,
  icon,
  onVerify,
}: {
  title: string
  subtitle: string
  detail?: string
  placeholder: string
  pending: boolean
  error: string | null
  icon: ReactNode
  onVerify: (note: string) => void
}) {
  const [open, setOpen] = useState(false)
  const [note, setNote] = useState("")
  const ready = note.trim().length > 0

  return (
    <li className="ml-card overflow-hidden">
      <div className="flex items-start gap-3 p-4">
        <span className="ml-icon-plate shrink-0 bg-n100 text-n700">
          {icon}
        </span>

        <div className="min-w-0 flex-1">
          <p className="truncate text-body-lg font-medium">{title}</p>
          <p className="mt-0.5 truncate text-body text-n700">{subtitle}</p>
          {detail && (
            <p className="mt-0.5 truncate text-body tabular-nums text-n700">
              {detail}
            </p>
          )}
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <Chip tone="unknown">Not yet verified</Chip>
          <button
            className="ml-btn-secondary ml-btn-sm"
            aria-expanded={open}
            onClick={() => setOpen((v) => !v)}
          >
            {open ? "Cancel" : "Review"}
          </button>
        </div>
      </div>

      {open && (
        <div className="border-t border-n200 bg-n100/40 p-4">
          <label className="block">
            <span className="ml-label block">Verification note</span>
            <textarea
              className="ml-field mt-1.5 min-h-[5rem]"
              placeholder={placeholder}
              value={note}
              autoFocus
              onChange={(e) => setNote(e.target.value)}
            />
          </label>

          {error && (
            <p className="mt-2 text-body text-danger" role="alert">
              {error}
            </p>
          )}

          <div className="mt-3 flex flex-wrap items-center gap-3">
            <button
              className="ml-btn-primary ml-btn-sm"
              // Disabled until a note exists: the note IS the verification,
              // and a one-click approve would make this a rubber stamp.
              disabled={!ready || pending}
              onClick={() => onVerify(note.trim())}
            >
              {pending ? "Verifying..." : "Verify"}
            </button>
            {!ready && (
              <span className="text-label text-n600">
                Write what you checked to enable this.
              </span>
            )}
          </div>
        </div>
      )}
    </li>
  )
}

function humanise(code: string) {
  return code.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase())
}
