import { useEffect, useState } from "react"
import { useI18n } from "../i18n"

export function OfflineBanner() {
  const { t } = useI18n()
  const [online, setOnline] = useState(navigator.onLine)

  useEffect(() => {
    const goOnline = () => setOnline(true)
    const goOffline = () => setOnline(false)
    window.addEventListener("online", goOnline)
    window.addEventListener("offline", goOffline)
    return () => {
      window.removeEventListener("online", goOnline)
      window.removeEventListener("offline", goOffline)
    }
  }, [])

  if (online) return null

  return (
    <p
      role="status"
      className="bg-warning px-4 py-2 text-center text-sm text-white"
    >
      {t("offline_banner")}
    </p>
  )
}
