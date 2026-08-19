import { useState } from "react"
import { Link } from "react-router-dom"
import { useMutation } from "@tanstack/react-query"
import { api } from "../api/client"
import { useI18n, LANGUAGES, LANGUAGE_LABELS, type Language } from "../i18n"
import { useAuth } from "../hooks/useAuth"
import { useGeolocation } from "../hooks/useGeolocation"
import { useInsurers } from "../hooks/useNearbyFacilities"

export function Profile() {
  const { t, setLang } = useI18n()
  const { session, setPatient, signOut } = useAuth()
  const { data: insurerData } = useInsurers()
  const { state: geo, locate } = useGeolocation()
  const [saved, setSaved] = useState(false)

  const save = useMutation({
    mutationFn: api.updateMe,
    onSuccess: (patient) => {
      setPatient(patient)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    },
  })

  if (session.state !== "signed_in") {
    return (
      <div className="mx-auto max-w-md px-4 pt-8 text-center">
        <p className="mb-4 text-sm text-neutral-600">{t("auth_prompt")}</p>
        <Link to="/sign-in" className="btn-primary w-full">
          {t("auth_sign_in")}
        </Link>
      </div>
    )
  }

  const patient = session.patient

  return (
    <div className="mx-auto max-w-md px-4 pb-24 pt-4">
      <h1 className="mb-4 text-xl font-semibold">{t("profile_title")}</h1>

      <div className="card space-y-4">
        <p className="text-sm text-neutral-500">
          {t("auth_phone")}: <span className="font-medium">{patient.phone}</span>
        </p>

        <label className="block">
          <span className="mb-1 block text-sm text-neutral-600">
            {t("profile_name")}
          </span>
          <input
            className="min-h-touch w-full rounded-lg border border-neutral-300 px-3"
            defaultValue={patient.full_name ?? ""}
            onBlur={(e) => save.mutate({ full_name: e.target.value })}
          />
        </label>

        <label className="block">
          <span className="mb-1 block text-sm text-neutral-600">
            {t("your_cover")}
          </span>
          <select
            className="min-h-touch w-full rounded-lg border border-neutral-300 px-2"
            value={patient.insurer ?? ""}
            onChange={(e) => save.mutate({ insurer: e.target.value || null })}
          >
            <option value="">{t("no_cover_set")}</option>
            {(insurerData?.results ?? []).map((i) => (
              <option key={i.code} value={i.code}>
                {i.name}
              </option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className="mb-1 block text-sm text-neutral-600">
            {t("profile_language")}
          </span>
          <select
            className="min-h-touch w-full rounded-lg border border-neutral-300 px-2"
            value={patient.language}
            onChange={(e) => {
              const next = e.target.value as Language
              setLang(next)
              save.mutate({ language: next })
            }}
          >
            {LANGUAGES.map((code) => (
              <option key={code} value={code}>
                {LANGUAGE_LABELS[code]}
              </option>
            ))}
          </select>
        </label>
      </div>

      {/* Opt-in, and the only thing that makes "leave home by" possible. */}
      <div className="card mt-4">
        <p className="text-sm font-medium">{t("profile_home_title")}</p>
        <p className="mt-1 text-sm text-neutral-500">{t("profile_home_why")}</p>
        <p className="mt-2 text-sm">
          {patient.home_location ? t("profile_home_set") : t("profile_home_unset")}
        </p>
        <button
          className="btn-secondary mt-3 w-full"
          onClick={() => {
            locate()
            if (geo.status === "ready") {
              save.mutate({
                home_location: { lat: geo.lat, lng: geo.lng },
              })
            }
          }}
        >
          {t("profile_home_use_current")}
        </button>
        {patient.home_location && (
          <button
            className="mt-2 w-full py-2 text-sm text-neutral-500"
            onClick={() => save.mutate({ home_location: null })}
          >
            {t("profile_home_clear")}
          </button>
        )}
      </div>

      {saved && (
        <p role="status" className="mt-3 text-center text-sm text-success">
          {t("profile_saved")}
        </p>
      )}

      <button className="btn-secondary mt-6 w-full" onClick={signOut}>
        {t("auth_sign_out")}
      </button>
    </div>
  )
}
