/**
 * MediLink UI primitives.
 *
 * Anything with behaviour or a variant lives here. Anything purely visual is a
 * class in design/base.css - dense provider tables read better as classNames
 * than as a wrapper component per cell.
 *
 * Kept dependency-free on purpose: a component library would add more to the
 * bundle than the eight primitives this product actually needs, and the
 * patient app has a 150 KB budget on a 3G connection.
 */

import {
  createContext,
  useContext,
  useId,
  useState,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
} from "react"

const cx = (...parts: Array<string | false | null | undefined>) =>
  parts.filter(Boolean).join(" ")

/* ------------------------------------------------------------------ Button */

type ButtonVariant = "primary" | "secondary" | "tertiary" | "destructive"

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant
  size?: "md" | "sm"
  loading?: boolean
  iconOnly?: boolean
  full?: boolean
}

const BUTTON_CLASS: Record<ButtonVariant, string> = {
  primary: "ml-btn-primary",
  secondary: "ml-btn-secondary",
  tertiary: "ml-btn-tertiary",
  destructive: "ml-btn-destructive",
}

export function Button({
  variant = "secondary",
  size = "md",
  loading = false,
  iconOnly = false,
  full = false,
  disabled,
  children,
  className,
  ...rest
}: ButtonProps) {
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      // Announce the busy state; a spinner alone tells a screen reader nothing.
      aria-busy={loading || undefined}
      className={cx(
        BUTTON_CLASS[variant],
        size === "sm" && "ml-btn-sm",
        iconOnly && "ml-btn-icon",
        full && "w-full",
        className,
      )}
    >
      {loading && <Spinner />}
      {children}
    </button>
  )
}

export function Spinner({ className }: { className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cx(
        // inline-block matters: a bare <span> is display:inline, where h-4/w-4
        // do nothing and this collapses to a 2px sliver. It only ever looked
        // right because every call site so far put it inside an inline-flex
        // button, which blockifies its children.
        "inline-block h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-current border-t-transparent opacity-70",
        className,
      )}
    />
  )
}

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
          "mb-1.5 block text-small font-medium text-ink",
          hideLabel && "sr-only",
        )}
      >
        {label}
      </label>
      {hint && (
        <p id={hintId} className="mb-1.5 text-small text-ink-muted">
          {hint}
        </p>
      )}
      {children(id, describedBy)}
      {error && (
        <p id={errorId} role="alert" className="mt-1.5 text-small text-danger">
          {error}
        </p>
      )}
    </div>
  )
}

export function TextInput({
  invalid,
  className,
  ...rest
}: InputHTMLAttributes<HTMLInputElement> & { invalid?: boolean }) {
  return (
    <input
      {...rest}
      aria-invalid={invalid || undefined}
      className={cx("ml-field", invalid && "ml-field-invalid", className)}
    />
  )
}

export function Select({
  invalid,
  className,
  children,
  ...rest
}: SelectHTMLAttributes<HTMLSelectElement> & { invalid?: boolean }) {
  return (
    <select
      {...rest}
      aria-invalid={invalid || undefined}
      className={cx("ml-field pr-8", invalid && "ml-field-invalid", className)}
    >
      {children}
    </select>
  )
}

/* -------------------------------------------------------------------- Chip */

export type ChipTone =
  | "success"
  | "warning"
  | "danger"
  | "info"
  | "neutral"
  | "unknown"

const CHIP_CLASS: Record<ChipTone, string> = {
  success: "ml-chip-success",
  warning: "ml-chip-warning",
  danger: "ml-chip-danger",
  info: "ml-chip-info",
  neutral: "ml-chip-neutral",
  unknown: "ml-chip-unknown",
}

/**
 * Status is never colour alone - the child text carries the meaning and the
 * tone only reinforces it. A colour-blind user, or anyone reading in bright
 * Kigali daylight, gets the same information.
 */
export function Chip({
  tone = "neutral",
  children,
  className,
}: {
  tone?: ChipTone
  children: ReactNode
  className?: string
}) {
  return <span className={cx(CHIP_CLASS[tone], className)}>{children}</span>
}

/* -------------------------------------------------------------------- Card */

export function Card({
  as: Tag = "div",
  interactive = false,
  className,
  children,
  ...rest
}: {
  as?: "div" | "article" | "section" | "li"
  interactive?: boolean
  className?: string
  children: ReactNode
} & Record<string, unknown>) {
  return (
    <Tag
      {...rest}
      className={cx(interactive ? "ml-card-interactive" : "ml-card", className)}
    >
      {children}
    </Tag>
  )
}

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

/* ------------------------------------------------------- Empty / error / info */

/**
 * An empty state always offers a way out. "No results" with no action is a
 * dead end, and a patient looking for care cannot afford one.
 */
export function EmptyState({
  title,
  body,
  action,
  icon,
}: {
  title: string
  body?: string
  action?: ReactNode
  icon?: ReactNode
}) {
  return (
    <div className="ml-card px-6 py-10 text-center">
      {icon && <div className="mb-3 flex justify-center text-ink-subtle">{icon}</div>}
      <p className="text-h3 font-semibold text-ink">{title}</p>
      {body && <p className="mx-auto mt-1.5 max-w-prose text-body text-ink-muted">{body}</p>}
      {action && <div className="mt-5 flex justify-center gap-2">{action}</div>}
    </div>
  )
}

/**
 * Errors are written for a patient, not a developer. The technical detail goes
 * to the console; the screen gets a sentence and a next step.
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
      className="rounded-xl border border-danger-border bg-danger-subtle p-4"
    >
      <p className="text-body font-medium text-danger">{title}</p>
      {body && <p className="mt-1 text-small text-ink-muted">{body}</p>}
      {action && <div className="mt-3 flex gap-2">{action}</div>}
    </div>
  )
}

export function Notice({
  tone = "info",
  children,
}: {
  tone?: "info" | "warning"
  children: ReactNode
}) {
  return (
    <p
      className={cx(
        "rounded-lg border px-3 py-2 text-small",
        tone === "info"
          ? "border-info-border bg-info-subtle text-info"
          : "border-warning-border bg-warning-subtle text-warning",
      )}
    >
      {children}
    </p>
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
      className="flex gap-1 overflow-x-auto border-b border-line"
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
        "-mb-px whitespace-nowrap border-b-2 px-3 py-2.5 text-body font-medium transition-colors",
        selected
          ? "border-primary text-primary"
          : "border-transparent text-ink-muted hover:text-ink",
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
