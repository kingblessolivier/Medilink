import { useI18n } from "../i18n"
import type { Facility } from "../api/types"

/**
 * One honest sentence under a list, instead of one per row.
 *
 * The honesty rule says a patient must never be shown a wait time we do not
 * have. It does not say we must say so six times on one screen: when almost
 * no facility reports live queue data, a per-card notice stops reading as
 * candour and starts reading as a broken widget repeated down the page.
 *
 * So the absence is stated once, under the list it applies to, and only when
 * it applies to the WHOLE list. If even one facility reports a real wait, the
 * note disappears and the difference between the cards carries the meaning -
 * which is the point of the `unknown` tone in the first place.
 */
export function NoLiveWaitNote({
  facilities,
  className,
}: {
  facilities: Facility[]
  className?: string
}) {
  const { t } = useI18n()

  if (facilities.length === 0) return null
  if (facilities.some((f) => f.wait.status === "available")) return null

  return (
    <p className={"text-body text-n700 " + (className ?? "")}>
      {t("wait_unavailable_list")}
    </p>
  )
}
