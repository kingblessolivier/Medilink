import { useI18n } from "../i18n"
import { useInsurers } from "../hooks/useNearbyFacilities"

type Props = {
  insurer?: string
  onChange: (code: string | undefined) => void
}

export function InsurerChip({ insurer, onChange }: Props) {
  const { t } = useI18n()
  const { data } = useInsurers()
  const options = data?.results ?? []
  const current = options.find((i) => i.code === insurer)

  return (
    <label className="card flex items-center justify-between gap-3">
      <span className="text-sm">
        <span className="text-neutral-500">{t("your_cover")}: </span>
        <span className="font-medium">
          {current ? current.name : t("no_cover_set")}
        </span>
      </span>
      <select
        className="min-h-touch rounded-lg border border-neutral-300 bg-white px-2 text-sm"
        value={insurer ?? ""}
        onChange={(e) => onChange(e.target.value || undefined)}
        aria-label={t("your_cover")}
      >
        <option value="">{t("change")}</option>
        {options.map((option) => (
          <option key={option.code} value={option.code}>
            {option.name}
          </option>
        ))}
      </select>
    </label>
  )
}
