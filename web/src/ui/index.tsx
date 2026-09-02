/**
 * MediLink UI primitives - the barrel.
 *
 * The fourteen primitives named in the design system each live in their own
 * module; this file re-exports the ones that are built and keeps the composite
 * pieces that are made out of them.
 *
 * Anything with behaviour or a variant is a component. Anything purely visual
 * is a class in design/base.css - dense workspace tables read better as
 * classNames than as a wrapper component per cell.
 *
 * Kept dependency-free on purpose: a component library would add more to the
 * bundle than the primitives this product actually needs, and the patient app
 * has a 150 KB budget on a 3G connection.
 *
 * All fourteen are built. `TextInput` and `Chip` remain as thin aliases of
 * `Input` and `Badge` so that existing call sites keep working; new code
 * should use the spec names.
 */

export { Avatar, type AvatarProps, type AvatarSize } from "./Avatar"
export { Badge, type BadgeProps, type BadgeTone } from "./Badge"
export { Button, type ButtonProps, type ButtonVariant, type ButtonSize } from "./Button"
export { Card, type CardProps, type CardVariant, type CardPadding } from "./Card"
export { EmptyState, type EmptyStateProps } from "./EmptyState"
export { FacilityCard as FacilityCardPrimitive, type FacilityCardProps } from "./FacilityCard"
export { Input, type InputProps } from "./Input"
export { InsuranceBadge, type InsuranceBadgeProps, type InsuranceStatus } from "./InsuranceBadge"
export { Modal, type ModalProps } from "./Modal"
export {
  QueuePositionDisplay,
  type QueuePositionDisplayProps,
} from "./QueuePositionDisplay"
export { Select, type SelectProps } from "./Select"
export { Spinner, type SpinnerProps, type SpinnerSize } from "./Spinner"
export { StatusPill, type QueueStatus, type StatusPillProps } from "./StatusPill"
export { Toast, type ToastProps, type ToastVariant } from "./Toast"

import { Badge } from "./Badge"
import { IconAlert, IconInfo } from "./icons"
import {
  createContext,
  useContext,
  useId,
  useState,
  type ReactNode,
} from "react"

const cx = (...parts: Array<string | false | null | undefined>) =>
  parts.filter(Boolean).join(" ")

/* ------------------------------------------------------------------- Field */

type FieldShellProps = {
  label: string
  hint?: string
  error?: string
  /** Hide the label visually but keep it for screen readers. */
  hideLabel?: boolean
  children: (id: string, describedBy?: string) => ReactNode
}

/** Wraps any control with a real <label>, a hint and an error. */
export function Field({
  label,
  hint,
  error,
  hideLabel = false,
  children,
}: FieldShellProps) {
  const id = useId()
  const hintId = hint ? `${id}-hint` : undefined
  const errorId = error ? `${id}-error` : undefined
  const describedBy = [hintId, errorId].filter(Boolean).join(" ") || undefined

  return (
    <div>
      <label
        htmlFor={id}
        className={cx(
          "mb-1.5 block text-body font-medium text-n900",
          hideLabel && "sr-only",
        )}
      >
        {label}
      </label>
      {hint && (
        <p id={hintId} className="mb-1.5 text-body text-n700">
          {hint}
        </p>
      )}
      {children(id, describedBy)}
      {error && (
        <p id={errorId} role="alert" className="mt-1.5 text-body text-danger">
          {error}
        </p>
      )}
    </div>
  )
}

/** Deprecated alias. New code imports `Input`. */
export { Input as TextInput } from "./Input"

/* -------------------------------------------------------------------- Chip */

/**
 * Deprecated alias. New code imports `Badge`.
 *
 * `info` maps to `primary`: the standard palette has no separate
 * informational colour, and the brand green is what carries that meaning
 * everywhere else in the product.
 */
export type ChipTone =
  | "success"
  | "warning"
  | "danger"
  | "info"
  | "neutral"
  | "unknown"

export function Chip({
  tone = "neutral",
  children,
  className,
}: {
  tone?: ChipTone
  children: ReactNode
  className?: string
}) {
  return (
    <Badge tone={tone === "info" ? "primary" : tone} className={className}>
      {children}
    </Badge>
  )
}

/* -------------------------------------------------------------------- Card */

/* --------------------------------------------------------------- Skeletons */

export function Skeleton({ className }: { className?: string }) {
  return <span aria-hidden="true" className={cx("ml-skeleton block", className)} />
}

/** Placeholder for a facility or doctor card while its data loads. */
export function CardSkeleton() {
  return (
    <div className="ml-card p-4">
      <Skeleton className="h-4 w-2/3" />
      <Skeleton className="mt-2.5 h-3 w-1/3" />
      <Skeleton className="mt-3 h-3 w-1/2" />
      <Skeleton className="mt-4 h-touch w-full rounded-md" />
    </div>
  )
}

export function ListSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-3" role="status" aria-label="Loading">
      {Array.from({ length: rows }, (_, i) => (
        <CardSkeleton key={i} />
      ))}
    </div>
  )
}

/**
 * Placeholder for a table while it loads. Used by the workspace and platform surfaces; the patient
 * screens have no tables, and a card skeleton standing in for a table row makes the layout
 * jump the moment the data lands.
 */
export function TableSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div
      className="overflow-hidden rounded-md border border-n200 bg-white"
      role="status"
      aria-label="Loading"
    >
      {Array.from({ length: rows }, (_, i) => (
        <div
          key={i}
          className="flex items-center gap-4 border-b border-n200 px-4 py-3 last:border-b-0"
        >
          <Skeleton className="h-3 w-12 shrink-0" />
          <Skeleton className="h-3 flex-1" />
          <Skeleton className="h-3 w-24 shrink-0" />
        </div>
      ))}
    </div>
  )
}

/* --------------------------------------------------------------------- Stat */

/**
 * One measured number, with room to say why it is missing.
 *
 * Three screens defined their own copy of this - Reports, the platform
 * Overview, and Care Guide monitoring - and they had already drifted apart on
 * spacing. Shared, because a facility manager comparing two of them is
 * comparing numbers, and inconsistent framing makes that harder than it
 * needs to be.
 *
 * `value` takes a string so a caller can pass an em dash. That is deliberate:
 * every one of these screens has a state where the honest answer is "not
 * enough data", and `hint` is where that gets explained rather than being
 * papered over with a zero.
 */
export function StatCard({
  label,
  value,
  hint,
  icon,
  tone = "neutral",
  chip,
}: {
  label: string
  value: string | number
  hint?: string
  icon?: ReactNode
  /** Tints only the icon plate. The number itself stays ink - a figure
   *  coloured green reads as "good", which is a judgement we cannot make. */
  tone?: "neutral" | "primary" | "warning" | "danger"
  chip?: ReactNode
}) {
  const plate = {
    neutral: "bg-n100 text-n700",
    primary: "bg-primary-light text-primary",
    warning: "bg-warning/10 text-warning",
    danger: "bg-danger/10 text-danger",
  }[tone]

  return (
    <div className="ml-card flex h-full flex-col p-4">
      <div className="flex items-start gap-3">
        {icon && <span className={cx("ml-icon-plate", plate)}>{icon}</span>}
        <p className="ml-label mt-1.5 min-w-0 flex-1">{label}</p>
      </div>
      <p className="mt-2 text-h1 tabular-nums">{value}</p>
      {chip && <div className="mt-2">{chip}</div>}
      {hint && <p className="mt-1.5 text-label text-n600">{hint}</p>}
    </div>
  )
}

/**
 * A labelled proportion bar.
 *
 * Illustrative only - the count beside it is the fact. Rendered with
 * `role="presentation"` for exactly that reason: a screen reader gets the
 * number, which is the part that means something.
 */
export function BarRow({
  label,
  count,
  max,
}: {
  label: string
  count: number
  max: number
}) {
  return (
    <li>
      <div className="flex items-baseline justify-between gap-3">
        <span className="min-w-0 truncate text-body-lg">{label}</span>
        <span className="shrink-0 tabular-nums text-body-lg font-medium text-n700">
          {count}
        </span>
      </div>
      <div
        className="mt-1.5 h-2 overflow-hidden rounded-full bg-n100"
        role="presentation"
      >
        <span
          className="block h-full rounded-full bg-primary transition-all duration-500"
          style={{ width: `${Math.max(2, Math.round((count / max) * 100))}%` }}
        />
      </div>
    </li>
  )
}

/* ------------------------------------------------------- Empty / error / info */

/**
 * An empty state always offers a way out. "No results" with no action is a
 * dead end, and a patient looking for care cannot afford one.
 */
/**
 * Nothing to show, said properly.
 *
 * Every empty state carries an icon now, and the caller does not have to
 * remember to pass one. A bare sentence centred in a 1160px white box is what
 * an empty state looks like when nobody designed it - and empty is a state
 * patients hit often, because a search with no results near them is a normal
 * Tuesday, not an error.
 *
 * The content is constrained even though the card is not. A card that shrinks
 * to its text breaks the grid it sits in; text that runs to 1160px is
 * unreadable. Constraining the inner column fixes both.
 */
/**
 * Errors are written for a patient, not a developer. The technical detail goes
 * to the console; the screen gets a sentence and a next step.
 *
 * The icon is not decoration. This box is tinted red, and colour alone must
 * never be what tells somebody a thing went wrong - a rule the status chips
 * have followed from the start, and this did not.
 */
export function ErrorState({
  title,
  body,
  action,
}: {
  title: string
  body?: string
  action?: ReactNode
}) {
  return (
    <div
      role="alert"
      className="flex gap-3 rounded-lg border border-danger/30 bg-danger/10 p-4"
    >
      <IconAlert size={18} className="mt-0.5 shrink-0 text-danger" />
      <div className="min-w-0 flex-1">
        <p className="text-body-lg font-medium text-danger">{title}</p>
        {body && <p className="mt-1 text-body text-n700">{body}</p>}
        {action && <div className="mt-3 flex flex-wrap gap-2">{action}</div>}
      </div>
    </div>
  )
}

/**
 * A standing remark about the screen - not an error, and not dismissible.
 *
 * Was a bare tinted paragraph. Same reasoning as ErrorState: the tint is the
 * only thing distinguishing an info notice from a warning, which fails
 * anybody who cannot separate the two hues.
 */
export function Notice({
  tone = "info",
  children,
}: {
  tone?: "info" | "warning"
  children: ReactNode
}) {
  const Glyph = tone === "info" ? IconInfo : IconAlert
  return (
    <div
      className={cx(
        "flex gap-2.5 rounded-md border px-3 py-2.5 text-body",
        tone === "info"
          ? "border-primary/30 bg-primary-light text-primary"
          : "border-warning/30 bg-warning/10 text-warning",
      )}
    >
      <Glyph size={16} className="mt-0.5 shrink-0" />
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  )
}

/* -------------------------------------------------------------------- Tabs */

type TabsContext = { value: string; setValue: (v: string) => void; name: string }
const TabsCtx = createContext<TabsContext | null>(null)

export function Tabs({
  defaultValue,
  children,
}: {
  defaultValue: string
  children: ReactNode
}) {
  const [value, setValue] = useState(defaultValue)
  const name = useId()
  return (
    <TabsCtx.Provider value={{ value, setValue, name }}>{children}</TabsCtx.Provider>
  )
}

export function TabList({ children }: { children: ReactNode }) {
  return (
    <div
      role="tablist"
      className="flex gap-1 overflow-x-auto border-b border-n200"
    >
      {children}
    </div>
  )
}

export function Tab({ value, children }: { value: string; children: ReactNode }) {
  const ctx = useContext(TabsCtx)
  if (!ctx) throw new Error("Tab must be used inside Tabs")
  const selected = ctx.value === value

  return (
    <button
      role="tab"
      id={`${ctx.name}-tab-${value}`}
      aria-selected={selected}
      aria-controls={`${ctx.name}-panel-${value}`}
      onClick={() => ctx.setValue(value)}
      className={cx(
        "-mb-px whitespace-nowrap border-b-2 px-3 py-2.5 text-body-lg font-medium transition-colors",
        selected
          ? "border-primary text-primary"
          : "border-transparent text-n700 hover:text-n900",
      )}
    >
      {children}
    </button>
  )
}

export function TabPanel({
  value,
  children,
}: {
  value: string
  children: ReactNode
}) {
  const ctx = useContext(TabsCtx)
  if (!ctx) throw new Error("TabPanel must be used inside Tabs")
  if (ctx.value !== value) return null

  return (
    <div
      role="tabpanel"
      id={`${ctx.name}-panel-${value}`}
      aria-labelledby={`${ctx.name}-tab-${value}`}
      className="pt-5"
    >
      {children}
    </div>
  )
}

export { cx }
