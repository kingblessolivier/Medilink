/**
 * Whether this browser has been through the S-01/S-02 introduction.
 *
 * Its own module, and a deliberately tiny one: App has to read this
 * synchronously to decide what "/" renders, and importing it from
 * routes/Welcome would drag that whole screen out of its lazy chunk and into
 * the main bundle - which is exactly the introduction that most visitors will
 * never see.
 */

const KEY = "medilink.welcome.seen"

export function hasSeenWelcome(): boolean {
  try {
    return window.localStorage.getItem(KEY) === "1"
  } catch {
    // Private browsing, or storage disabled. Showing the introduction a
    // second time is a far smaller failure than crashing the first screen.
    return false
  }
}

export function markWelcomeSeen(): void {
  try {
    window.localStorage.setItem(KEY, "1")
  } catch {
    /* ignore - see above */
  }
}
