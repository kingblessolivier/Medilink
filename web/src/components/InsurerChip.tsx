import { useI18n } from "../i18n"
import { useInsurers } from "../hooks/useNearbyFacilities"
import { IconShieldCheck } from "../ui/icons"

type Props = {
  insurer?: string
  onChange: (code: string | undefined) => void
}

/**
 * The insurer preference, shown wherever it changes what a patient sees.
 *
 * Two bugs this replaces:
 *
 * The empty option was labelled "change" - so the item that reads as the verb
 * for opening the menu was in fact the one that CLEARED your insurer. Picking
 * it looked like a no-op and silently widened every result.
 *
 * The row was `flex-wrap justify-between`, which at 360px put a long
 * Kinyarwanda label ("Ubwishingizi bwawe: Ntabwo warashyiraho ubwishingizi")
 * against a select and clipped it. It stacks below `sm` now.
 *
 * The wording is rule 6: what a facility ACCEPTS, never that a patient is
 * covered. Setting this filters the directory; it does not promise anything.
 */
export function InsurerChip({ insurer, onChange }: Props) {
  const { t } = useI18n()
  const { data } = useInsurers()
  const options = data?.results ?? []
  const current = options.find((i) => i.code === insurer)

  return (
    <div className="ml-card max-w-xl p-4">
      <div className="flex items-start gap-3">
        <span className="ml-icon-plate shrink-0 bg-primary-subtle text-primary">
          <IconShieldCheck size={18} />
        </span>

        <div className="min-w-0 flex-1">
          <p className="ml-label">{t("your_cover")}</p>
          <p className="mt-0.5 truncate text-body font-medium">
            {current ? current.name : t("no_cover_set")}
          </p>
        </div>
      </div>

      <label className="mt-3 block">
        <span className="sr-only">{t("your_cover")}</span>
        <select
          className="ml-field"
          value={insurer ?? ""}
          onChange={(e) => onChange(e.target.value || undefined)}
        >
          {/* Says what choosing it DOES. "Change" described the menu, not the
              option, and clearing your insurer by accident widens every
              result without saying so. */}
          <option value="">{t("cover_none")}</option>
          {options.map((option) => (
            <option key={option.code} value={option.code}>
              {option.name}
            </option>
          ))}
        </select>
      </label>
    </div>
  )
}
