import { useState } from "react"
import { Link } from "react-router-dom"
import { useMutation } from "@tanstack/react-query"
import { api } from "../api/client"
import { useI18n, LANGUAGES, LANGUAGE_LABELS, type Language } from "../i18n"
import { useAuth } from "../hooks/useAuth"
import { ErrorState } from "../ui"
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

  // `patient` is null for staff and admins as well as for anonymous
  // visitors: they are signed in, but not as a patient, and this screen edits
  // a patient's own record. Sending them to sign in would be a loop, so they
  // get the same prompt with an honest reason.
  if (session.state !== "signed_in" || session.patient === null) {
    return (
      <div className="mx-auto max-w-md px-4 pt-8 text-center">
        {/* Every page states where it is. Without an h1 a screen-reader user
            has nothing to jump to and no idea which screen they landed on. */}
        <h1 className="mb-2 text-h1">{t("profile_title")}</h1>
        <p className="mb-4 text-small text-ink-muted">{t("auth_prompt")}</p>
        <Link to="/sign-in" className="ml-btn-primary w-full">
          {t("auth_sign_in")}
        </Link>
      </div>
    )
  }

  const patient = session.patient

  return (
    <div className="mx-auto max-w-md px-4 pb-24 pt-4">
      <h1 className="mb-4 text-h1">{t("profile_title")}</h1>

      <div className="ml-card space-y-4 p-4">
        <p className="text-small text-ink-muted">
          {t("auth_phone")}: <span className="font-medium">{patient.phone}</span>
        </p>

        <label className="block">
          <span className="mb-1 block text-small text-ink-muted">
            {t("profile_name")}
          </span>
          <input
            className="ml-field"
            defaultValue={patient.full_name ?? ""}
            onBlur={(e) => save.mutate({ full_name: e.target.value })}
          />
        </label>

        <label className="block">
          <span className="mb-1 block text-small text-ink-muted">
            {t("your_cover")}
          </span>
          <select
            className="ml-field"
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
          <span className="mb-1 block text-small text-ink-muted">
            {t("profile_language")}
          </span>
          <select
            className="ml-field"
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
      <div className="ml-card mt-4 p-4">
        <p className="text-small font-medium">{t("profile_home_title")}</p>
        <p className="mt-1 text-small text-ink-muted">{t("profile_home_why")}</p>
        <p className="mt-2 text-small">
          {patient.home_location ? t("profile_home_set") : t("profile_home_unset")}
        </p>
        <button
          className="ml-btn-secondary mt-3 w-full"
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
            className="mt-2 w-full py-2 text-small text-ink-muted"
            onClick={() => save.mutate({ home_location: null })}
          >
            {t("profile_home_clear")}
          </button>
        )}
      </div>

      {saved && (
        <p role="status" className="mt-3 text-center text-small text-success">
          {t("profile_saved")}
        </p>
      )}

      {/* Fields save on blur, so a silent failure is indistinguishable from a
          success: the patient looks at their new name on screen and believes
          it was kept. Surfaced, and it names the field that did not save. */}
      {save.isError && (
        <div className="mt-3">
          <ErrorState
            title={t("profile_save_failed")}
            action={
              <button
                className="ml-btn-secondary ml-btn-sm"
                onClick={() => save.mutate(save.variables!)}
              >
                {t("retry")}
              </button>
            }
          />
        </div>
      )}

      <button className="ml-btn-secondary mt-6 w-full" onClick={signOut}>
        {t("auth_sign_out")}
      </button>
    </div>
  )
}
