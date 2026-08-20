import { useQuery } from "@tanstack/react-query"
import { api } from "../api/client"

/**
 * Whether the Care Guide may be offered at all.
 *
 * The backend gate returns 503 until a named clinician has signed off a
 * protocol. The client must HIDE the entry points entirely when that is the
 * case - showing a button that errors would be worse than showing nothing,
 * and worse still would be implying the feature exists when no clinician has
 * reviewed it. See docs/08 section 8.
 */
export function useTriageStatus() {
  const query = useQuery({
    queryKey: ["triage", "status"],
    queryFn: api.triageStatus,
    staleTime: 5 * 60_000,
    retry: 1,
  })

  return {
    ...query,
    // Default to hidden. If we cannot tell, we do not offer it.
    available: query.data?.available === true,
    reason: query.data?.reason ?? "",
  }
}
