import { useEffect, useId, useMemo, useRef, useState } from "react"
import { useNavigate } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { api } from "../api/client"
import { useI18n } from "../i18n"
import { Spinner } from "../ui"
import { formatDistance } from "../lib/format"
import type { Coordinates, SearchGroup, SearchResult } from "../api/types"

/**
 * One search box over everything.
 *
 * Built as a proper combobox rather than a text field with a panel under it:
 * a patient using a screen reader or a keyboard has to be able to hear how
 * many results arrived and move through them. That means real `role` and
 * `aria-activedescendant` wiring, not a div with an onClick.
 *
 * Debounced at 250 ms. Every keystroke hitting the API would be wasteful on a
 * metered connection and would make results flicker as slower responses
 * arrived out of order.
 */

const DEBOUNCE_MS = 250
const MIN_CHARS = 2

const GROUP_LABEL: Record<SearchGroup["kind"], string> = {
  insurer: "group_insurers",
  specialty: "group_specialties",
  service: "group_services",
  provider: "group_doctors",
  facility: "group_facilities",
}

export function GlobalSearch({
  coords,
  autoFocus = false,
}: {
  coords: Coordinates | null
  autoFocus?: boolean
}) {
  const { t, lang } = useI18n()
  const navigate = useNavigate()
  const listId = useId()

  const [term, setTerm] = useState("")
  const [debounced, setDebounced] = useState("")
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const root = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(term.trim()), DEBOUNCE_MS)
    return () => clearTimeout(timer)
  }, [term])

  const query = useQuery({
    queryKey: ["search", debounced, coords],
    queryFn: () =>
      api.search({ q: debounced, lat: coords?.lat, lng: coords?.lng }),
    enabled: debounced.length >= MIN_CHARS,
    staleTime: 60_000,
  })

  // One flat list behind the grouped display, so arrow keys move through
  // results in reading order rather than jumping between groups.
  const flat = useMemo(() => {
    const rows: Array<{ group: SearchGroup["kind"]; result: SearchResult }> = []
    for (const group of query.data?.groups ?? []) {
      for (const result of group.results) rows.push({ group: group.kind, result })
    }
    return rows
  }, [query.data])

  useEffect(() => setActive(0), [flat.length])

  // Close when focus or a click leaves the combobox entirely.
  useEffect(() => {
    function onPointerDown(event: MouseEvent) {
      if (!root.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener("mousedown", onPointerDown)
    return () => document.removeEventListener("mousedown", onPointerDown)
  }, [])

  function go(result: SearchResult) {
    setOpen(false)
    setTerm("")
    navigate(result.href)
  }

  function onKeyDown(event: React.KeyboardEvent) {
    if (event.key === "Escape") {
      setOpen(false)
      return
    }
    if (!flat.length) return

    if (event.key === "ArrowDown") {
      event.preventDefault()
      setActive((i) => (i + 1) % flat.length)
    } else if (event.key === "ArrowUp") {
      event.preventDefault()
      setActive((i) => (i - 1 + flat.length) % flat.length)
    } else if (event.key === "Enter") {
      event.preventDefault()
      const chosen = flat[active]
      if (chosen) go(chosen.result)
    }
  }

  const label = (result: SearchResult) => {
    if (lang === "rw" && result.label_rw) return result.label_rw
    if (lang === "fr" && result.label_fr) return result.label_fr
    return result.label
  }

  const showPanel = open && debounced.length >= MIN_CHARS
  let index = -1

  return (
    <div ref={root} className="relative">
      <div className="relative">
        <input
          type="search"
          role="combobox"
          aria-expanded={showPanel}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={
            showPanel && flat[active] ? `${listId}-${active}` : undefined
          }
          autoFocus={autoFocus}
          value={term}
          onChange={(e) => {
            setTerm(e.target.value)
            setOpen(true)
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKeyDown}
          placeholder={t("search_placeholder")}
          aria-label={t("search_placeholder")}
          className="ml-field h-12 pl-4 pr-10 text-body-lg"
        />
        {query.isFetching && (
          <span className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-subtle">
            <Spinner />
          </span>
        )}
      </div>

      {/* Result count for screen readers - a sighted user sees the list. */}
      <p className="sr-only" role="status">
        {showPanel ? t("n_results", { n: flat.length }) : ""}
      </p>

      {showPanel && (
        <div
          id={listId}
          role="listbox"
          aria-label={t("search_placeholder")}
          className="absolute inset-x-0 top-full z-30 mt-1 max-h-96 overflow-auto rounded-xl border border-line bg-surface py-1 shadow-overlay"
        >
          {query.isLoading && (
            <p className="px-4 py-3 text-small text-ink-muted">{t("loading")}</p>
          )}

          {query.data && flat.length === 0 && (
            <p className="px-4 py-3 text-small text-ink-muted">
              {t("search_no_matches", { term: debounced })}
            </p>
          )}

          {(query.data?.groups ?? []).map((group) => (
            <div key={group.kind}>
              <p className="ml-label px-4 pb-1 pt-2.5">
                {t(GROUP_LABEL[group.kind])}
              </p>
              {group.results.map((result) => {
                index += 1
                const position = index
                return (
                  <button
                    key={`${group.kind}-${result.code}`}
                    id={`${listId}-${position}`}
                    role="option"
                    aria-selected={position === active}
                    type="button"
                    // Not disabled: an unroutable specialty is still worth
                    // showing, it just cannot lead anywhere useful.
                    disabled={!result.routable}
                    onMouseEnter={() => setActive(position)}
                    onClick={() => go(result)}
                    className={
                      "flex w-full items-baseline justify-between gap-3 px-4 py-2 text-left transition-colors " +
                      (position === active ? "bg-primary-subtle" : "") +
                      (result.routable ? "" : " opacity-50")
                    }
                  >
                    <span className="min-w-0">
                      <span className="block truncate text-body text-ink">
                        {label(result)}
                      </span>
                      {result.sublabel && (
                        <span className="block truncate text-small text-ink-muted">
                          {result.sublabel}
                        </span>
                      )}
                    </span>
                    {typeof result.distance_m === "number" && (
                      <span className="shrink-0 text-small text-ink-muted">
                        {formatDistance(result.distance_m, t("distance_nearby"))}
                      </span>
                    )}
                  </button>
                )
              })}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
