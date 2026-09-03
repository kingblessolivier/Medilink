/**
 * FA-10, staff accounts, per docs/02_dashboards.html.
 *
 * Until this existed only a MediLink platform admin could add a receptionist,
 * so onboarding a facility meant someone at MediLink creating each account by
 * hand. A clinic that hires a receptionist on a Monday should not have to
 * write to us.
 *
 * ADMINISTRATORS ONLY, and the API enforces it rather than this screen. A
 * receptionist works the queue all day; minting accounts is a different power,
 * and `IsFacilityAdmin` checks the role directly instead of reusing
 * `can_manage_queue`, which deliberately includes receptionists.
 *
 * THE TEMPORARY PASSWORD IS SHOWN ONCE. It is generated rather than chosen -
 * an administrator inventing passwords for colleagues picks the clinic name
 * and a digit - and it is never stored readable or shown again. The panel says
 * so at the moment it appears, because that is the only moment it can be
 * copied.
 */

import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api, ApiRequestError } from "../api/client"
import type { TeamMember } from "../api/types"
import { Badge, Button, Card, ErrorState, Notice, TableSkeleton } from "../ui"

const ROLES = [
  { value: "receptionist", label: "Receptionist" },
  { value: "clinician", label: "Clinician" },
  { value: "admin", label: "Facility administrator" },
] as const

export function WorkspaceTeam() {
  const queryClient = useQueryClient()
  const team = useQuery({ queryKey: ["staff", "team"], queryFn: api.staffTeam })

  const [username, setUsername] = useState("")
  const [fullName, setFullName] = useState("")
  const [role, setRole] = useState<string>("receptionist")
  /** Held only until the administrator navigates away. Never re-fetchable. */
  const [issued, setIssued] = useState<{ username: string; password: string } | null>(
    null,
  )
  const [error, setError] = useState<string | null>(null)

  const refresh = () =>
    queryClient.invalidateQueries({ queryKey: ["staff", "team"] })

  const create = useMutation({
    mutationFn: () =>
      api.staffTeamCreate({ username, full_name: fullName, role }),
    onSuccess: (member) => {
      setIssued({
        username: member.username,
        password: member.temporary_password,
      })
      setUsername("")
      setFullName("")
      setError(null)
      refresh()
    },
    onError: (e) =>
      setError(
        e instanceof ApiRequestError
          ? e.message
          : "Could not create that account.",
      ),
  })

  const update = useMutation({
    mutationFn: ({ id, body }: { id: number; body: { role?: string; active?: boolean } }) =>
      api.staffTeamUpdate(id, body),
    onSuccess: () => {
      setError(null)
      refresh()
    },
    onError: (e) =>
      setError(
        e instanceof ApiRequestError ? e.message : "Could not apply that change.",
      ),
  })

  if (team.isLoading) return <TableSkeleton rows={4} />
  if (team.isError) {
    // 403 here means a receptionist reached the URL directly. Say which it is.
    const denied =
      team.error instanceof ApiRequestError && team.error.status === 403
    return (
      <ErrorState
        title={denied ? "Administrators only" : "Could not load staff accounts."}
        body={
          denied
            ? "Only a facility administrator can manage staff accounts."
            : undefined
        }
      />
    )
  }

  const members = team.data ?? []

  return (
    <div>
      <h1 className="text-h1 text-n900">Staff accounts</h1>
      <p className="mt-1 text-body text-n700">
        Who can sign in at this facility, and as what.
      </p>

      {error && (
        <div className="mt-4">
          <Notice tone="warning">{error}</Notice>
        </div>
      )}

      {/* Shown once, immediately after creation. */}
      {issued && (
        <Card variant="selected" className="mt-4 p-4">
          <p className="text-body-lg font-medium text-n900">
            Account created for {issued.username}
          </p>
          <p className="mt-1 text-body text-n700">
            Give them this temporary password now and ask them to change it. It
            is not stored and cannot be shown again.
          </p>
          <p className="mt-3 select-all rounded-md border border-n300 bg-white px-3 py-2 font-mono text-h3 tabular-nums text-n900">
            {issued.password}
          </p>
          <Button
            variant="secondary"
            size="sm"
            className="mt-3"
            onClick={() => setIssued(null)}
          >
            Done
          </Button>
        </Card>
      )}

      <div className="mt-6 grid gap-4 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <Card className="overflow-hidden p-0">
          <div className="ml-scroll-x">
            <table className="ml-table">
              <thead>
                <tr>
                  <th scope="col">Username</th>
                  <th scope="col">Name</th>
                  <th scope="col">Role</th>
                  <th scope="col">Access</th>
                </tr>
              </thead>
              <tbody>
                {members.map((member: TeamMember) => (
                  <tr key={member.id}>
                    <td className="font-mono text-body">{member.username}</td>
                    <td>{member.full_name || <span className="text-n600">—</span>}</td>
                    <td>
                      <select
                        className="ml-field h-9 min-h-0 py-0 text-body"
                        value={member.role}
                        disabled={member.is_self || update.isPending}
                        onChange={(e) =>
                          update.mutate({
                            id: member.id,
                            body: { role: e.target.value },
                          })
                        }
                      >
                        {ROLES.map((r) => (
                          <option key={r.value} value={r.value}>
                            {r.label}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td>
                      {member.is_self ? (
                        // The API refuses this too; disabling it here means an
                        // administrator never has to discover that by failing.
                        <Badge tone="neutral">You</Badge>
                      ) : (
                        <Button
                          variant={member.active ? "danger" : "secondary"}
                          size="sm"
                          loading={update.isPending}
                          onClick={() =>
                            update.mutate({
                              id: member.id,
                              body: { active: !member.active },
                            })
                          }
                        >
                          {member.active ? "Switch off" : "Switch on"}
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        <Card className="h-fit p-4">
          <h2 className="text-h3 text-n900">Add someone</h2>
          <form
            className="mt-3 space-y-3"
            onSubmit={(e) => {
              e.preventDefault()
              create.mutate()
            }}
          >
            <label className="block">
              <span className="mb-1 block text-body text-n700">Username</span>
              <input
                className="ml-field"
                value={username}
                required
                autoComplete="off"
                onChange={(e) => setUsername(e.target.value.toLowerCase())}
                placeholder="reception2"
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-body text-n700">
                Full name (optional)
              </span>
              <input
                className="ml-field"
                value={fullName}
                autoComplete="off"
                onChange={(e) => setFullName(e.target.value)}
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-body text-n700">Role</span>
              <select
                className="ml-field"
                value={role}
                onChange={(e) => setRole(e.target.value)}
              >
                {ROLES.map((r) => (
                  <option key={r.value} value={r.value}>
                    {r.label}
                  </option>
                ))}
              </select>
            </label>
            <Button
              type="submit"
              variant="primary"
              full
              loading={create.isPending}
              disabled={username.trim().length < 3}
            >
              Create account
            </Button>
            <p className="text-body text-n600">
              A temporary password is generated and shown once.
            </p>
          </form>
        </Card>
      </div>
    </div>
  )
}

export default WorkspaceTeam
