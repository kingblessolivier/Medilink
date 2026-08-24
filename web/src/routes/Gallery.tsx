import { useState } from "react"
import {
  Button,
  Card,
  CardSkeleton,
  Chip,
  EmptyState,
  ErrorState,
  Field,
  ListSkeleton,
  Notice,
  Select,
  Skeleton,
  Spinner,
  Tab,
  TabList,
  TabPanel,
  Tabs,
  TextInput,
} from "../ui"
import { WaitLine } from "../components/WaitLine"
import { useI18n } from "../i18n"

/**
 * Every primitive, every state, on one page.
 *
 * This exists because of a specific failure that happened three times. When
 * `index.css` became the design-system import, the old `card` / `field` /
 * `btn-primary` classes stopped existing, and any screen not touched since
 * kept using them - so the sign-in button, the entrance to everything behind
 * authentication, rendered as plain unstyled text. Nothing failed. Type checks
 * passed, tests passed, the build was green, and the button looked broken.
 *
 * A page that renders one of everything makes that visible in two seconds.
 * Open it after any change to `design/`.
 *
 * Not linked from anywhere and not in the nav: it is a developer tool that
 * happens to live at a URL. It carries no patient data and calls no API.
 */
export function Gallery() {
  const { lang, setLang } = useI18n()
  const [value, setValue] = useState("")

  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-6 pb-24">
      <h1 className="text-h1">Component gallery</h1>
      <p className="mt-1 text-body text-ink-muted">
        One of everything, in every state. If something here looks unstyled,
        the design system is not reaching the app.
      </p>
      <p className="mt-2 text-caption text-ink-subtle">
        Language: {lang.toUpperCase()} —{" "}
        <button className="underline" onClick={() => setLang(lang === "rw" ? "en" : "rw")}>
          switch
        </button>{" "}
        to check that nothing here breaks when the strings get longer.
      </p>

      {/* ------------------------------------------------------------ type */}
      <Section title="Type scale">
        <p className="text-h1">Heading 1 — Ubuvuzi bwegereye</p>
        <p className="text-h2">Heading 2 — Amavuriro hafi yawe</p>
        <p className="text-h3">Heading 3 — Dr Uwase Alice</p>
        <p className="text-body-lg">Body large — about 25 minutes</p>
        <p className="text-body">Body — the ordinary paragraph size.</p>
        <p className="text-small text-ink-muted">Small, muted — 2.4 km away</p>
        <p className="text-caption text-ink-subtle">Caption, subtle — updated 3 min ago</p>
        <p className="ml-label">Label — uppercase section heading</p>
        <p className="text-queue tabular-nums">8</p>
      </Section>

      {/* --------------------------------------------------------- buttons */}
      <Section title="Buttons">
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="primary">Primary</Button>
          <Button variant="secondary">Secondary</Button>
          <Button variant="tertiary">Tertiary</Button>
          <Button variant="destructive">Destructive</Button>
          <Button>No variant (defaults to secondary)</Button>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button disabled>Disabled</Button>
          <Button loading>Loading</Button>
          <button className="ml-btn-primary ml-btn-sm">Small (36px)</button>
          <button className="ml-btn-secondary ml-btn-sm">Small secondary</button>
        </div>
        <p className="text-caption text-ink-subtle">
          `variant` defaults to <strong>secondary</strong>, not primary: a
          button nobody thought about should not claim the emphasis of the
          one action on the screen. Full-size buttons are 44px. `ml-btn-sm` is
          36px — WCAG 2.5.8 but not 2.5.5, so secondary and inline only.
        </p>
      </Section>

      {/* ---------------------------------------------------------- inputs */}
      <Section title="Inputs">
        {/* Field is a render-prop: it owns the id so the label, the hint and
            the error can all be wired to the control by aria. */}
        <Field label="Text input" hint="With a hint underneath.">
          {(id, describedBy) => (
            <TextInput
              id={id}
              aria-describedby={describedBy}
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder="078..."
            />
          )}
        </Field>
        <Field label="Invalid" error="That phone number is not recognised.">
          {(id, describedBy) => (
            <TextInput
              id={id}
              aria-describedby={describedBy}
              value="0788"
              onChange={() => {}}
              invalid
            />
          )}
        </Field>
        <Field label="Select">
          {(id) => (
            <Select id={id} value="" onChange={() => {}}>
              <option value="">All services</option>
              <option value="general_consultation">General consultation</option>
            </Select>
          )}
        </Field>
        <label className="flex min-h-touch items-center gap-2">
          <input type="checkbox" className="ml-checkbox" />
          <span className="text-body">Checkbox in a 44px label row</span>
        </label>
      </Section>

      {/* ----------------------------------------------------------- chips */}
      <Section title="Chips">
        <div className="flex flex-wrap gap-2">
          <Chip tone="success">Open now</Chip>
          <Chip tone="warning">Closing soon</Chip>
          <Chip tone="danger">Closed</Chip>
          <Chip tone="info">Bookable</Chip>
          <Chip tone="neutral">Mutuelle de Sante</Chip>
          <Chip tone="unknown">Not confirmed</Chip>
        </div>
        <p className="text-caption text-ink-subtle">
          `unknown` must be the quietest thing on the screen. If it draws the
          eye more than `neutral`, the palette has drifted.
        </p>
      </Section>

      {/* ------------------------------------------------------- wait line */}
      <Section title="Wait line — the honesty rule, made visual">
        <div className="space-y-2">
          <WaitLine wait={{ status: "available", minutes: 25, people_waiting: 8, as_of: new Date().toISOString() }} />
          <WaitLine wait={{ status: "insufficient_data", minutes: null, people_waiting: null, as_of: new Date().toISOString() }} />
          <WaitLine wait={{ status: "not_reported", minutes: null, people_waiting: null, as_of: new Date().toISOString() }} />
          <WaitLine wait={{ status: "closed", minutes: null, people_waiting: null, as_of: new Date().toISOString() }} />
        </div>
        <p className="text-caption text-ink-subtle">
          Only the first of these is a number. The other three must never look
          like an estimate a patient could act on.
        </p>
      </Section>

      {/* ----------------------------------------------------------- cards */}
      <Section title="Cards">
        <Card className="p-4">
          <p className="text-body font-medium">Static card</p>
          <p className="mt-1 text-small text-ink-muted">
            Cards are for facilities, doctors, appointments and summaries. Not
            for laying out a page.
          </p>
        </Card>
        <Card interactive className="p-4">
          <p className="text-body font-medium">Interactive card</p>
          <p className="mt-1 text-small text-ink-muted">Hover me.</p>
        </Card>
      </Section>

      {/* -------------------------------------------------------- loading */}
      <Section title="Loading">
        <Spinner />
        <Skeleton className="h-4 w-2/3" />
        <CardSkeleton />
        <ListSkeleton rows={2} />
      </Section>

      {/* --------------------------------------------------- empty / error */}
      <Section title="Empty, error, notice">
        <EmptyState
          title="No facilities within 5 km."
          body="Try a wider search or pick a district."
          action={<Button size="sm">Widen the search</Button>}
        />
        <ErrorState
          title="Could not load facilities."
          body="Check your connection."
          action={
            <Button variant="secondary" size="sm">
              Try again
            </Button>
          }
        />
        <Notice tone="info">Informational.</Notice>
        <Notice tone="warning">Something needs attention.</Notice>
      </Section>

      {/* ------------------------------------------------------------ tabs */}
      <Section title="Tabs">
        <Tabs defaultValue="services">
          <TabList>
            <Tab value="services">Services</Tab>
            <Tab value="hours">Opening hours</Tab>
            <Tab value="insurance">Insurance</Tab>
          </TabList>
          <TabPanel value="services">
            <p className="pt-3 text-body">Services panel.</p>
          </TabPanel>
          <TabPanel value="hours">
            <p className="pt-3 text-body">Hours panel.</p>
          </TabPanel>
          <TabPanel value="insurance">
            <p className="pt-3 text-body">Insurance panel.</p>
          </TabPanel>
        </Tabs>
      </Section>

      {/* ----------------------------------------------------------- table */}
      <Section title="Table">
        <div className="ml-scroll-x rounded-lg border border-line bg-surface">
          <table className="ml-table">
            <thead>
              <tr>
                <th scope="col">Ticket</th>
                <th scope="col">Patient</th>
                <th scope="col">Waited</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td className="font-mono">G-104</td>
                <td>A. Uwase</td>
                <td className="tabular-nums">18 min</td>
              </tr>
              <tr data-selected="true">
                <td className="font-mono">G-105</td>
                <td>E. Mugisha</td>
                <td className="tabular-nums">9 min</td>
              </tr>
            </tbody>
          </table>
        </div>
      </Section>

      {/* --------------------------------------------------------- colours */}
      <Section title="Colour — green is not the interface">
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Swatch className="bg-primary text-white" label="primary" />
          <Swatch className="bg-primary-subtle text-primary" label="primary-subtle" />
          <Swatch className="bg-surface text-ink" label="surface" />
          <Swatch className="bg-surface-sunken text-ink" label="surface-sunken" />
          <Swatch className="bg-success-subtle text-success" label="success" />
          <Swatch className="bg-warning-subtle text-warning" label="warning" />
          <Swatch className="bg-danger-subtle text-danger" label="danger" />
          <Swatch className="bg-unknown-subtle text-unknown" label="unknown" />
        </div>
        <p className="text-caption text-ink-subtle">
          Green carries availability, verification, success and the primary
          action. Nothing else. If a green thing here means none of those, it
          is wrong.
        </p>
      </Section>
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="ml-section">
      <h2 className="text-h3 mb-3">{title}</h2>
      <div className="space-y-3">{children}</div>
    </section>
  )
}

function Swatch({ className, label }: { className: string; label: string }) {
  return (
    <div
      className={`flex h-16 items-center justify-center rounded-lg border border-line text-caption ${className}`}
    >
      {label}
    </div>
  )
}
