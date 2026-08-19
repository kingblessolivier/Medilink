import { useMemo, useState } from "react"
import { useNavigate, useParams, useSearchParams } from "react-router-dom"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api, ApiRequestError } from "../api/client"
import { useI18n } from "../i18n"
import { useAuth } from "../hooks/useAuth"
import { useServiceTypes } from "../hooks/useNearbyFacilities"

export function Book() {
  const { slug = "" } = useParams()
  const [params] = useSearchParams()
  const { t, lang } = useI18n()
  const navigate = useNavigate()
  const { session } = useAuth()
  const queryClient = useQueryClient()

  const [service, setService] = useState(
    params.get("service") ?? "general_consultation",
  )
  const [error, setError] = useState<string | null>(null)

  const { data: serviceData } = useServiceTypes()
  const facility = useQuery({
    queryKey: ["facility", slug],
    queryFn: () => api.facility(slug),
  })

  const slots = useQuery({
    queryKey: ["slots", slug, service],
    queryFn: () => api.slots(slug, { service }),
    // Capacity changes as other patients book; do not serve a stale grid.
    staleTime: 15_000,
  })

  const booking = useMutation({
    mutationFn: (slotStart: string) =>
      api.book({ facility: slug, service, slot_start: slotStart }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["appointments"] })
      navigate("/visits")
    },
    onError: (err) =>
      setError(err instanceof ApiRequestError ? err.message : t("error_generic")),
  })

  const label = useMemo(() => {
    const found = serviceData?.results.find((s) => s.code === service)
    if (!found) return service
    return lang === "rw" ? found.name_rw : lang === "fr" ? found.name_fr : found.name_en
  }, [serviceData, service, lang])

  if (session.state !== "signed_in") {
    return (
      <div className="mx-auto max-w-md px-4 pt-8 text-center">
        <p className="mb-4 text-sm text-neutral-600">{t("auth_needed_to_book")}</p>
        <button className="btn-primary w-full" onClick={() => navigate("/sign-in")}>
          {t("auth_sign_in")}
        </button>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-md px-4 pb-24 pt-4">
      <h1 className="text-xl font-semibold">{facility.data?.name ?? slug}</h1>
      <p className="mb-4 text-sm text-neutral-500">{label}</p>

      <label className="card mb-4 block">
        <span className="mb-1 block text-sm text-neutral-600">
          {t("filter_service")}
        </span>
        <select
          className="min-h-touch w-full rounded-lg border border-neutral-300 px-2"
          value={service}
          onChange={(e) => setService(e.target.value)}
        >
          {(facility.data?.services ?? []).map((s) => (
            <option key={s.code} value={s.code}>
              {lang === "rw" ? s.name_rw : lang === "fr" ? s.name_fr : s.name_en}
            </option>
          ))}
        </select>
      </label>

      {error && (
        <p className="mb-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-danger">
          {error}
        </p>
      )}

      {slots.isLoading && <p className="text-sm text-neutral-500">{t("loading")}</p>}

      {slots.data?.days.length === 0 && (
        <p className="card p-4 text-sm text-neutral-600">{t("book_no_slots")}</p>
      )}

      {slots.data?.days.map((day) => (
        <section key={day.date} className="mb-4">
          <h2 className="mb-2 text-sm font-semibold text-neutral-600">
            {new Date(day.date).toLocaleDateString([], {
              weekday: "long",
              day: "numeric",
              month: "short",
            })}
          </h2>
          <div className="grid grid-cols-3 gap-2">
            {day.slots.map((slot) => {
              const full = slot.remaining === 0
              return (
                <button
                  key={slot.start}
                  disabled={full || booking.isPending}
                  onClick={() => {
                    setError(null)
                    booking.mutate(slot.start)
                  }}
                  className={
                    "min-h-touch rounded-lg border text-sm " +
                    (full
                      ? "cursor-not-allowed border-neutral-200 bg-neutral-100 text-neutral-400"
                      : "border-neutral-300 bg-white hover:border-primary hover:text-primary")
                  }
                >
                  {new Date(slot.start).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </button>
              )
            })}
          </div>
        </section>
      ))}
    </div>
  )
}
