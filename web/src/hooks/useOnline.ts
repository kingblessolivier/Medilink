import { useEffect, useState } from "react"

/**
 * Whether the browser thinks it has a connection.
 *
 * Extracted from OfflineBanner because two components now need it, and a
 * second copy of an event-listener effect is how they drift apart.
 *
 * `navigator.onLine` is a weak signal - it reports the network interface, not
 * whether anything is reachable - so it is used only to explain what the user
 * is already seeing, never to decide whether to attempt a request. React
 * Query does that, and it does it by trying.
 */
export function useOnline(): boolean {
  const [online, setOnline] = useState(
    () => typeof navigator === "undefined" || navigator.onLine,
  )

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

  return online
}
