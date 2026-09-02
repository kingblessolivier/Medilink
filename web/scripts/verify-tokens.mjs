/**
 * Guards the one thing tokens.css cannot enforce about itself.
 *
 * Every colour is declared twice - once as a hex for hand-written CSS, once as
 * space-separated channels so Tailwind can apply an opacity modifier. Nothing
 * in CSS ties the two together, so a hex edited without its `-rgb` twin
 * produces a build where `bg-primary` and `bg-primary/50` are different
 * colours, and neither the compiler nor the tests say a word.
 *
 * Run by `npm run verify:tokens`, and by `npm test` before the suite.
 */
import { readFileSync } from "node:fs"
import { fileURLToPath } from "node:url"
import { dirname, join } from "node:path"

const here = dirname(fileURLToPath(import.meta.url))
const tokensPath = join(here, "..", "src", "styles", "tokens.css")
const css = readFileSync(tokensPath, "utf8")

/** The sixteen colours the roadmap's `:root` block defines. */
const EXPECTED_COLOURS = [
  "primary",
  "primary-dark",
  "primary-light",
  "accent",
  "danger",
  "success",
  "warning",
  "n900",
  "n800",
  "n700",
  "n600",
  "n400",
  "n300",
  "n200",
  "n100",
  "white",
]

const hexes = new Map()
const channels = new Map()

for (const [, name, value] of css.matchAll(
  /--([a-z0-9-]+):\s*(#[0-9A-Fa-f]{6})\s*;/g,
)) {
  hexes.set(name, value.toUpperCase())
}
for (const [, name, value] of css.matchAll(
  /--([a-z0-9-]+)-rgb:\s*(\d{1,3} \d{1,3} \d{1,3})\s*;/g,
)) {
  channels.set(name, value)
}

const failures = []

for (const name of EXPECTED_COLOURS) {
  const hex = hexes.get(name)
  if (!hex) {
    failures.push(`--${name} is missing its hex declaration`)
    continue
  }
  const derived = [1, 3, 5]
    .map((i) => Number.parseInt(hex.slice(i, i + 2), 16))
    .join(" ")
  const declared = channels.get(name)
  if (!declared) {
    failures.push(`--${name}-rgb is missing (hex is ${hex})`)
  } else if (declared !== derived) {
    failures.push(
      `--${name}-rgb is "${declared}" but ${hex} is "${derived}" - the pair has drifted`,
    )
  }
}

// A hex with no channel twin is a colour Tailwind cannot fade, which is the
// bug this script exists to catch. Catch it for tokens added later too, not
// only the sixteen above.
for (const [name, hex] of hexes) {
  if (!EXPECTED_COLOURS.includes(name) && !channels.has(name)) {
    failures.push(`--${name} (${hex}) has no --${name}-rgb twin`)
  }
}

if (failures.length > 0) {
  console.error("tokens.css failed verification:\n")
  for (const f of failures) console.error(`  - ${f}`)
  console.error("")
  process.exit(1)
}

console.log(
  `tokens.css OK - ${EXPECTED_COLOURS.length} colours, each hex matching its channel twin.`,
)
