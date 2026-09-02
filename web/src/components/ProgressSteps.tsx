import { useEffect, useState } from "react"
import { Spinner } from "../ui"

/**
 * What is happening, rather than "Loading…".
 *
 * The brief asks for the Care Guide to say "Reviewing your responses /
 * Checking care pathways / Finding suitable specialists" instead of a bare
 * spinner, and it is right that "Loading…" tells somebody nothing while they
 * wait on a health question.
 *
 * **It does not fake the wait.** The triage engine is a deterministic lookup -
 * no model, no inference - so on a good connection the answer comes back in
 * milliseconds. Playing a four-second sequence of reassuring steps over that
 * would be inventing work to look intelligent, which is the same dishonesty
 * as inventing a wait time.
 *
 * So the steps are paced by the ACTUAL request. The first is shown
 * immediately; each later one appears only if the request is still running
 * when its turn comes. On a fast connection a patient sees one line and it is
 * gone. On 3G, which is what this product is built for, they get the
 * informative sequence the brief describes - because the wait is real.
 */

const STEP_MS = 900

export function ProgressSteps({
  steps,
  className,
}: {
  steps: string[]
  className?: string
}) {
  const [reached, setReached] = useState(0)

  useEffect(() => {
    if (reached >= steps.length - 1) return
    const timer = setTimeout(() => setReached((n) => n + 1), STEP_MS)
    return () => clearTimeout(timer)
  }, [reached, steps.length])

  const current = steps[Math.min(reached, steps.length - 1)]

  return (
    <div
      className={className}
      // One live region for the whole sequence, so a screen reader announces
      // each step as it changes rather than re-reading the list.
      role="status"
      aria-live="polite"
    >
      <p className="flex items-center gap-2 text-body-lg text-n900">
        <Spinner />
        {current}
      </p>

      {/* The steps already passed, so somebody who looks up mid-wait can see
          where they are rather than just the current line. */}
      {reached > 0 && (
        <ol className="mt-2 space-y-0.5">
          {steps.slice(0, reached).map((step) => (
            <li key={step} className="text-body text-n600">
              {step}
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}
