/**
 * EmptyState.
 *
 * A dead end always names the way out. An empty list with no action is a
 * screen a patient cannot leave without using the back button.
 */

import type { ReactNode } from "react"
import { IconSearch } from "./icons"

export type EmptyStateProps = {
  title: string
  body?: string
  action?: ReactNode
  icon?: ReactNode
}

export function EmptyState({ title, body, action, icon }: EmptyStateProps) {
  return (
    <div className="ml-card px-6 py-10 text-center">
      <div className="mx-auto flex max-w-sm flex-col items-center">
        <span className="ml-icon-plate h-11 w-11 bg-n100 text-n600">
          {icon ?? <IconSearch size={20} />}
        </span>
        <p className="mt-4 text-h3 text-n900">{title}</p>
        {body && <p className="mt-1.5 text-body-lg text-n700">{body}</p>}
        {/* The action is the way OUT of a dead end, so it is full size even
            when the caller passed a small button. Callers set that for dense
            rows; an empty state is the opposite of dense, and on a phone this
            is often the only thing on the screen worth tapping.

            Done here rather than by editing sixteen call sites, so the next
            empty state gets it without anybody remembering. */}
        {action && (
          <div className="mt-5 flex flex-wrap justify-center gap-2 [&_.ml-control-sm]:h-touch [&_.ml-control-sm]:px-4 [&_.ml-control-sm]:text-body-lg">
            {action}
          </div>
        )}
      </div>
    </div>
  )
}

export default EmptyState
