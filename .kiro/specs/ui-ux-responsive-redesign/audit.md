# UI/UX Audit — Elevator PDM Operations Console (`frontend/`)

Stage 1 deliverable for the `ui-ux-responsive-redesign` spec. This audit enumerates UI/UX
issues found in the current `frontend/` React + TypeScript implementation. It is produced
**before** any production UI code changes (audit-first sequencing). No source code is modified
by this document.

## Scope and method

Every source file and route under `frontend/src/` was read in full and inspected for issues in
five categories. Each issue below follows the `AuditIssue` record shape defined in `design.md`:

```
AuditIssue {
  id            // stable unique, e.g. "A-001"
  location      // file path when from a source file, route name when from a rendered route
  severity      // exactly one of: critical | major | minor
  category      // exactly one of: visual-design | layout-responsiveness
                //                 | navigation-ia | accessibility | data-state-feedback
  wcagCriterion // required when category === "accessibility" (WCAG 2.1 success criterion)
  description
  recommendation
}
```

### Severity legend

- **critical** — Blocks a core task or excludes a class of users (keyboard/AT users, mobile users)
  or can cause an operator to misread safety-relevant status.
- **major** — Significantly degrades usability, accessibility conformance, or maintainability, but
  the task can still be completed.
- **minor** — Polish, robustness, or consistency gap with limited user impact.

### Category legend

`visual-design` · `layout-responsiveness` · `navigation-ia` · `accessibility` · `data-state-feedback`

### Mandated findings (Requirement 1.4, 1.5, 1.6)

These three findings are required to be recorded explicitly by the task; they are captured below
with the IDs noted here for traceability:

- **Missing shared `Design_Token` definitions in `index.css`** → **A-001** (Requirement 1.4).
- **Non-collapsible `Navigation_Shell` on Mobile** → **A-011** (Requirement 1.5).
- **Each color-only `Status_Indicator` instance** → **A-015** (fleet status),
  **A-025** (alert severity), **A-026** (maintenance status) (Requirement 1.6).

---

## Issues

### `frontend/src/index.css`

#### A-001 — No shared design tokens (hard-coded literals throughout)
- **location:** `frontend/src/index.css`
- **severity:** major
- **category:** visual-design
- **description:** The single global stylesheet (~640 lines) hard-codes every visual value as a
  literal: colors (`#102126`, `#143f49`, `rgba(16,33,38,0.09)`, `#87e4db`, …), spacing
  (`2rem`, `1.5rem`, `0.75rem`, …), border-radii (`1rem`, `1.25rem`, `999px`, …), font sizes
  (`0.78rem`, `1.8rem`, …), and shadows (`0 18px 38px rgba(33,70,80,0.08)`). There is no
  single source of truth, so the same color/spacing/radius is repeated dozens of times and cannot
  be themed or adjusted consistently. (Explicitly required by Requirement 1.4.)
- **recommendation:** Introduce a `tokens.css` defining CSS custom properties for color, typography,
  spacing, border-radius, elevation, and motion; replace literals with `var(--token)` references.

#### A-002 — No theming; locked to light color-scheme
- **location:** `frontend/src/index.css`
- **severity:** major
- **category:** visual-design
- **description:** `:root` is locked to `color-scheme: light` with a fixed gradient background and
  fixed dark sidebar. There is no dark theme, no `[data-theme]` hook, and no
  `prefers-color-scheme` handling, so the console cannot adapt to user/OS preference or varied
  lighting.
- **recommendation:** Drive colors from theme-scoped tokens overridden under `[data-theme="dark"]`;
  resolve initial theme from stored preference → OS scheme → light default.

#### A-003 — Low-contrast muted text
- **location:** `frontend/src/index.css`
- **severity:** major
- **category:** accessibility
- **wcagCriterion:** WCAG 1.4.3 Contrast (Minimum) (AA)
- **description:** Several muted foreground colors over light/translucent surfaces are at risk of
  falling below the 4.5:1 ratio for normal text — e.g. `.toolbar__meta { color:#49656d }`,
  `.metric-list dt { color:#5f7b83 }`, `.fleet-card__eyebrow { color:#56757e }`, and sidebar
  muted text `rgba(246,251,250,0.76)`/`0.82` over the semi-transparent `rgba(9,33,40,0.92)`
  panel. Translucent backgrounds make the effective ratio depend on whatever sits behind them.
- **recommendation:** Define text/muted-text tokens with verified ≥4.5:1 contrast against their
  surface tokens in each theme; avoid translucent text/background pairings for body copy.

#### A-004 — No visible focus indicator
- **location:** `frontend/src/index.css`
- **severity:** critical
- **category:** accessibility
- **wcagCriterion:** WCAG 2.4.7 Focus Visible (AA)
- **description:** The stylesheet defines no `:focus`/`:focus-visible` styling for links, buttons,
  inputs, selects, textareas, or nav links. Focus styling relies entirely on inconsistent browser
  defaults, and several interactive elements have custom backgrounds that can obscure the default
  ring — keyboard users cannot reliably tell where focus is.
- **recommendation:** Add a token-driven, high-contrast `:focus-visible` outline (≥3:1 against
  adjacent colors) to every interactive element.

#### A-005 — Status/graphical elements lack guaranteed non-text contrast
- **location:** `frontend/src/index.css`
- **severity:** minor
- **category:** accessibility
- **wcagCriterion:** WCAG 1.4.11 Non-text Contrast (AA)
- **description:** Status badge fills (`rgba(49,125,89,0.12)`, `rgba(184,122,16,0.14)`,
  `rgba(167,42,42,0.14)`) and the many `rgba(16,33,38,0.08–0.10)` borders are very low-opacity, so
  the graphical boundaries that distinguish cards, fields, and badges may not reach 3:1 against
  their backgrounds.
- **recommendation:** Use solid border/graphical tokens meeting ≥3:1 non-text contrast.

#### A-006 — Breakpoints do not match the defined responsive bands
- **location:** `frontend/src/index.css`
- **severity:** major
- **category:** layout-responsiveness
- **description:** Responsive behavior is driven by only two ad-hoc `max-width` queries (960px and
  720px). The spec's bands are Mobile (<640), Tablet (640–1023), Desktop (1024–1439), and
  Large_Desktop (≥1440). The current thresholds collapse the sidebar at 960px and stack grids at
  720px, which does not align to Mobile/Tablet/Desktop and leaves Tablet (640–720) showing
  multi-column grids intended for larger viewports.
- **recommendation:** Re-key layout to the four defined breakpoints; single column at Mobile,
  ≤2 columns at Tablet, multi-column at Desktop+.

#### A-007 — No Large_Desktop content cap or centering
- **location:** `frontend/src/index.css`
- **severity:** minor
- **category:** layout-responsiveness
- **description:** `.app-shell` content column is `minmax(0,1fr)` and `.content` has no
  `max-width`, so on Large_Desktop (≥1440px) the primary content stretches edge-to-edge with no
  1440px cap and no horizontal centering, hurting readability on wide monitors.
- **recommendation:** Cap the primary content region at 1440px and center it at Large_Desktop.

#### A-008 — Animation ignores reduced-motion preference
- **location:** `frontend/src/index.css`
- **severity:** minor
- **category:** accessibility
- **wcagCriterion:** WCAG 2.3.3 Animation from Interactions (the applicable motion criterion; project Requirement 6.10)
- **description:** The `live-pulse` keyframe animation on `.chart-card__pulse` (and the various
  `transform`/`transition` hover effects) run unconditionally; there is no
  `@media (prefers-reduced-motion: reduce)` block to disable non-essential animation.
- **recommendation:** Wrap motion tokens/animations so they collapse to `0ms`/none under
  `prefers-reduced-motion: reduce`.

### `frontend/src/App.tsx`

#### A-009 — Document title never updates per route
- **location:** `frontend/src/App.tsx`
- **severity:** minor
- **category:** accessibility
- **wcagCriterion:** WCAG 2.4.2 Page Titled (A)
- **description:** The router renders four routes inside `AppShell` but never sets a route-specific
  document title, so the browser tab / AT announcement stays static across Fleet, Live, Alerts, and
  Config.
- **recommendation:** Set a descriptive `document.title` per route (e.g. "Fleet Overview · Elevator
  PDM").

#### A-010 — No top-level error boundary
- **location:** `frontend/src/App.tsx`
- **severity:** minor
- **category:** data-state-feedback
- **description:** There is no React error boundary around the routes. An uncaught render error in
  any page (e.g. an unexpected payload shape) unmounts the whole console with a blank screen and no
  recovery affordance.
- **recommendation:** Wrap routed content in an error boundary that shows a recoverable error state.

### `frontend/src/components/layout/AppShell.tsx`

#### A-011 — Navigation does not collapse on Mobile/Tablet
- **location:** `frontend/src/components/layout/AppShell.tsx`
- **severity:** critical
- **category:** navigation-ia
- **description:** `AppShell` renders a permanently expanded sidebar with the full nav list. The
  only responsive behavior is the CSS rule `@media (max-width:960px){ .app-shell{ grid-template-columns:1fr } }`,
  which stacks the sidebar **above** the content but never collapses the navigation behind a menu
  control. On Mobile/Tablet the brand block plus four full-width nav links consume a large band of
  vertical space before any monitoring content is visible, and there is no menu toggle. (Explicitly
  required by Requirement 1.5.)
- **recommendation:** Replace with a `NavigationShell` that is a persistent sidebar at
  Desktop/Large_Desktop and collapses behind a single menu control at Mobile/Tablet.

#### A-012 — Internal endpoint URL surfaced on every route (sidebar)
- **location:** `frontend/src/components/layout/AppShell.tsx`
- **severity:** major
- **category:** data-state-feedback
- **description:** The sidebar brand block renders `<code>{apiBaseUrl}</code>` and a
  default/custom-endpoint pill. Because `AppShell` wraps all routes, the internal REST base URL is
  shown on Fleet, Live, Alerts, and Config — Requirement 7.8 restricts internal endpoint URLs to
  the Local Config route only.
- **recommendation:** Remove the endpoint URL/status from the shared shell; surface it only on
  `/config`.

#### A-013 — No skip-to-content link
- **location:** `frontend/src/components/layout/AppShell.tsx`
- **severity:** major
- **category:** accessibility
- **wcagCriterion:** WCAG 2.4.1 Bypass Blocks (A)
- **description:** The shell offers no "skip to main content" link, so keyboard and screen-reader
  users must tab through the brand block and all nav links on every route before reaching the page
  content.
- **recommendation:** Add a visible-on-focus skip link that targets the `<main>` content region.

#### A-014 — Active nav link not clearly distinguished from hover
- **location:** `frontend/src/components/layout/AppShell.tsx`
- **severity:** minor
- **category:** navigation-ia
- **description:** `.nav__link--active` shares the exact rule block with `.nav__link:hover`
  (same background, border color, and `translateX`). The active route is therefore visually
  identical to a hovered link, and the only persistent active cue is `aria-current` emitted by
  `NavLink`. Requirement 5.7 wants the active link distinguished from non-active links by a
  non-color means that is distinct from the hover affordance.
- **recommendation:** Give the active link a dedicated persistent treatment (e.g. left rail
  indicator + heavier weight) separate from the hover style.

### `frontend/src/pages/FleetOverviewPage.tsx` — route `/fleet`

#### A-015 — Color-only elevator status indicator
- **location:** `frontend/src/pages/FleetOverviewPage.tsx`
- **severity:** critical
- **category:** accessibility
- **wcagCriterion:** WCAG 1.4.1 Use of Color (A)
- **description:** `getStatusTone()` maps an elevator's status/health score to
  `.status-badge--healthy/--warning/--critical`, which differ **only** by background and text
  color. The badge text is the raw `status` string (or `"UNKNOWN"`), not the healthy/warning/
  critical tone — so when tone is derived from `latest_health_score` (e.g. score 60 → amber, score
  40 → red while the label still reads "UNKNOWN"), the severity is conveyed by color alone, with no
  icon, shape, or tone text. (Explicitly required by Requirement 1.6.)
- **recommendation:** Use a `StatusBadge` that pairs color with a distinct icon/shape and an
  explicit tone label for each state.

#### A-016 — Internal endpoint URL surfaced on the Fleet route
- **location:** `/fleet` (route)
- **severity:** major
- **category:** data-state-feedback
- **description:** The "Data source" card renders `<code>{apiBaseUrl}/elevators</code>`, exposing
  the internal REST endpoint on a non-Config route, contrary to Requirement 7.8.
- **recommendation:** Remove the endpoint string from this route; describe the data source without
  the raw URL.

#### A-017 — Data-state changes are not announced to assistive tech
- **location:** `frontend/src/pages/FleetOverviewPage.tsx`
- **severity:** major
- **category:** accessibility
- **wcagCriterion:** WCAG 4.1.3 Status Messages (AA)
- **description:** Loading ("Loading elevator summaries…"), empty, and error states render as plain
  `.callout` text with no `aria-live` region, so screen-reader users are not notified when the view
  transitions between loading/error/populated.
- **recommendation:** Route loading/error messages through polite/assertive live regions via a
  shared announcer.

#### A-018 — Error state offers no retry and no degraded-data affordance
- **location:** `/fleet` (route)
- **severity:** major
- **category:** data-state-feedback
- **description:** On request failure the page shows "Unable to load fleet data. {error}" with no
  retry control. Requirement 7.4 requires an error that names the view, states the reason, and
  presents a retry control while preserving previously loaded data.
- **recommendation:** Add a retry control and a standardized error presentation that preserves the
  last successful data.

#### A-019 — Loading feedback is undifferentiated plain text
- **location:** `frontend/src/pages/FleetOverviewPage.tsx`
- **severity:** minor
- **category:** data-state-feedback
- **description:** Loading is a bare text callout with no spinner/skeleton and no guaranteed
  300ms-visible indicator; the initial `isLoading` state and the 10s polling refresh give no clear
  "refreshing" cue.
- **recommendation:** Use a shared `DataState` loading presentation with a prompt visual indicator.

### `frontend/src/pages/LiveMonitorPage.tsx` — route `/live`

#### A-020 — Connection indicator has no distinct per-state visual treatment
- **location:** `/live` (route)
- **severity:** major
- **category:** data-state-feedback
- **description:** Connection state is shown as a neutral `.status-pill` containing free-text
  ("Connecting" / "Live" / "Socket error" / "Disconnected"). All states use the same pill styling —
  there is no color/icon differentiation, and four ad-hoc strings are used instead of the three
  canonical connected/connecting/disconnected treatments required by Requirement 7.7.
- **recommendation:** Normalize to three mutually distinct connection treatments (connected /
  connecting / disconnected) combining color with icon/label, updated within 1s.

#### A-021 — Internal endpoint URLs surfaced on the Live route
- **location:** `/live` (route)
- **severity:** major
- **category:** data-state-feedback
- **description:** The toolbar prints `History: {readingsUrl}` and `Socket: {socketUrl}`, exposing
  the full REST and WebSocket URLs on a non-Config route, contrary to Requirement 7.8.
- **recommendation:** Remove the raw URLs from this route.

#### A-022 — Synthetic vs live data is not a persistent per-chart label
- **location:** `frontend/src/pages/LiveMonitorPage.tsx`
- **severity:** minor
- **category:** data-state-feedback
- **description:** Interpolated points are produced (`source: "synthetic"`) and the only indication
  is a "Signal source: Interpolated live trace / Live packet" field buried in the metric banner.
  The charts themselves draw synthetic and live points with identical styling and carry no
  persistent label, so a viewer cannot tell which trace is synthetic. Requirement 7.6 wants a
  persistent label distinguishing synthetic from live packet data.
- **recommendation:** Render a persistent per-chart label/marking whenever the displayed series
  contains interpolated points.

#### A-023 — Unguarded `JSON.parse` on WebSocket messages
- **location:** `frontend/src/pages/LiveMonitorPage.tsx`
- **severity:** minor
- **category:** data-state-feedback
- **description:** `socket.onmessage` calls `JSON.parse(event.data)` with no try/catch. A malformed
  or partial frame throws inside the handler instead of being skipped, which can disrupt the live
  view. (The subsequent `!readings || !timestamp` guard only runs after a successful parse.)
- **recommendation:** Wrap parsing in try/catch and skip unparseable frames without throwing.

#### A-024 — Live/loading data changes are not announced
- **location:** `frontend/src/pages/LiveMonitorPage.tsx`
- **severity:** minor
- **category:** accessibility
- **wcagCriterion:** WCAG 4.1.3 Status Messages (AA)
- **description:** "Loading reading history…", the empty-readings message, and error callouts render
  without any live region, so AT users are not informed of history-load and error transitions.
- **recommendation:** Announce loading politely and errors assertively via the shared announcer.

### `frontend/src/pages/AlertsMaintenancePage.tsx` — route `/alerts`

#### A-025 — Color-only (and misleading) alert severity indicator
- **location:** `frontend/src/pages/AlertsMaintenancePage.tsx`
- **severity:** critical
- **category:** accessibility
- **wcagCriterion:** WCAG 1.4.1 Use of Color (A)
- **description:** `getAlertTone()` maps severity to color-only badge classes; the tone is conveyed
  solely by color with no icon/shape. The mapping is also misleading: `CRITICAL` is rendered with
  the **warning/amber** treatment and only `EMERGENCY` gets the critical/red treatment, so the most
  severe non-emergency alerts can be visually under-weighted on a safety-relevant ops view.
  (Explicitly required by Requirement 1.6.)
- **recommendation:** Use a `StatusBadge` with color + icon + label, and a severity→tone mapping
  where CRITICAL reads as critical.

#### A-026 — Color-only maintenance status indicator
- **location:** `frontend/src/pages/AlertsMaintenancePage.tsx`
- **severity:** major
- **category:** accessibility
- **wcagCriterion:** WCAG 1.4.1 Use of Color (A)
- **description:** `getMaintenanceTone()` maps `completed/cancelled/scheduled/pending` to badge
  classes that differ only by color (with `pending` falling back to an undifferentiated neutral
  badge). State is conveyed by color alone, with no icon/shape signal. (Explicitly required by
  Requirement 1.6.)
- **recommendation:** Render maintenance status via a `StatusBadge` combining color with icon/label.

#### A-027 — Internal endpoint URLs surfaced on the Alerts route
- **location:** `/alerts` (route)
- **severity:** major
- **category:** data-state-feedback
- **description:** The toolbar meta prints `Alerts: {apiBaseUrl}/alerts` and
  `Maintenance: {apiBaseUrl}/maintenance`, exposing internal endpoints on a non-Config route,
  contrary to Requirement 7.8.
- **recommendation:** Remove the raw endpoint strings from this route.

#### A-028 — Form validation errors not associated with their inputs
- **location:** `frontend/src/pages/AlertsMaintenancePage.tsx`
- **severity:** major
- **category:** accessibility
- **wcagCriterion:** WCAG 3.3.1 Error Identification (A)
- **description:** Validation failures (e.g. "Maintenance requires an elevator and a reason.",
  "Technician name is required…") are pushed into a single shared top-of-page `setError` callout.
  The message is not linked to the offending field via `aria-describedby`, the fields carry no
  `aria-invalid`, and the message is not placed in a live region, so AT users may not perceive which
  input failed. (Project Requirement 6.8.)
- **recommendation:** Associate each validation message with its input through `aria-describedby`
  exposing the full text and set `aria-invalid` on the field.

#### A-029 — Checkbox touch target below 44px
- **location:** `frontend/src/pages/AlertsMaintenancePage.tsx`
- **severity:** minor
- **category:** accessibility
- **wcagCriterion:** WCAG 2.5.5 Target Size (the applicable target-size criterion; project Requirement 6.5)
- **description:** The "Include acknowledged alerts" checkbox is styled `.checkbox input { width:1rem; height:1rem }`
  (~16px), well below the 44×44px minimum hit area required by Requirement 6.5.
- **recommendation:** Expand the interactive hit area (control + label) to at least 44×44px.

#### A-030 — Action errors not announced; no retry on load failure
- **location:** `/alerts` (route)
- **severity:** minor
- **category:** data-state-feedback
- **description:** Acknowledge/create/update failures and the initial load error all funnel into one
  plain top callout with no live-region announcement and no retry control; loading is plain text.
- **recommendation:** Use the shared `DataState`/announcer with a retry control for load failures.

### `frontend/src/pages/ConfigPage.tsx` — route `/config`

> Note: surfacing the API base URL, socket URL, and defaults **on this route is correct** per
> Requirement 7.8 and is not flagged.

#### A-031 — Save/test feedback not in a live region
- **location:** `frontend/src/pages/ConfigPage.tsx`
- **severity:** major
- **category:** accessibility
- **wcagCriterion:** WCAG 4.1.3 Status Messages (AA)
- **description:** Save/restore/test-connection outcomes are rendered into a `.callout` driven by
  `feedback` state without `aria-live`, so success/error results (including async test-connection
  results) are not announced to screen-reader users.
- **recommendation:** Render feedback in a polite (success) / assertive (error) live region.

#### A-032 — Validation messages not programmatically tied to inputs
- **location:** `frontend/src/pages/ConfigPage.tsx`
- **severity:** major
- **category:** accessibility
- **wcagCriterion:** WCAG 3.3.1 Error Identification (A)
- **description:** Field-level validation (e.g. "API base URL and API key are both required.",
  "API base URL must be a valid absolute HTTP or HTTPS URL.") is shown only in the shared feedback
  callout; the `apiBaseUrl`/`apiKey` inputs have no `aria-describedby`, `aria-invalid`, or explicit
  id/`for` association to the message. (Project Requirement 6.8.)
- **recommendation:** Wire each validation message to its field via `aria-describedby` and set
  `aria-invalid`.

#### A-033 — API key shown in plaintext and echoed in the defaults card
- **location:** `frontend/src/pages/ConfigPage.tsx`
- **severity:** minor
- **category:** data-state-feedback
- **description:** The API key is entered in a `type="text"` input and the default key is printed in
  the "Built-in defaults" card (`<code>{defaultConfig.apiKey}</code>`). For a credential value this
  is a shoulder-surfing/UX concern.
- **recommendation:** Mask the key field (with a reveal toggle) and avoid printing the literal
  default key.

### `frontend/src/components/charts/MetricSparkline.tsx`

#### A-034 — Chart exposes only a generic text alternative
- **location:** `frontend/src/components/charts/MetricSparkline.tsx`
- **severity:** major
- **category:** accessibility
- **wcagCriterion:** WCAG 1.1.1 Non-text Content (A)
- **description:** The SVG uses `role="img"` with `aria-label={`${label} trend`}` and no `<title>`/
  `<desc>`. The accessible name conveys nothing about the data — it omits the latest value, the unit,
  and the timestamp of the latest sample (Requirement 6.9), so screen-reader users get no telemetry
  information from the chart.
- **recommendation:** Generate an accessible text alternative containing the latest value, unit, and
  the timestamp of the latest value.

#### A-035 — Chart colors/fills hard-coded as literals
- **location:** `frontend/src/components/charts/MetricSparkline.tsx`
- **severity:** minor
- **category:** visual-design
- **description:** The component receives stroke colors as raw hex props
  (`#0f7c82`, `#d07a14`, `#196f47`, `#9c2f2f` from `LiveMonitorPage`) and hard-codes the background
  `fill="rgba(10,38,44,0.02)"`, bypassing any token system and preventing theming of the charts.
- **recommendation:** Drive chart colors from design tokens (status/metric palette) so charts theme
  with the rest of the console.

---

## Coverage list (Requirement 1.9, 1.10)

All files and routes examined during the audit, with the count of issues recorded against each.
Entries with `issueCount: 0` are recorded explicitly as examined-with-zero-issues.

### Source files

| location | issueCount | issue IDs |
|---|---|---|
| `frontend/src/index.css` | 8 | A-001, A-002, A-003, A-004, A-005, A-006, A-007, A-008 |
| `frontend/src/App.tsx` | 2 | A-009, A-010 |
| `frontend/src/main.tsx` | 0 | — (examined: entry/bootstrap only, no UI/UX issue) |
| `frontend/src/vite-env.d.ts` | 0 | — (examined: type declarations only) |
| `frontend/src/lib/api.ts` | 0 | — (examined: fixed REST contract; no presentation issue) |
| `frontend/src/lib/ws.ts` | 0 | — (examined: pure URL builders; no presentation issue) |
| `frontend/src/lib/localConfig.ts` | 0 | — (examined: config store/hook; no presentation issue) |
| `frontend/src/components/layout/AppShell.tsx` | 4 | A-011, A-012, A-013, A-014 |
| `frontend/src/components/charts/MetricSparkline.tsx` | 2 | A-034, A-035 |
| `frontend/src/pages/FleetOverviewPage.tsx` | 4 | A-015, A-017, A-019, (route: A-016, A-018) |
| `frontend/src/pages/LiveMonitorPage.tsx` | 4 | A-022, A-023, A-024, (route: A-020, A-021) |
| `frontend/src/pages/AlertsMaintenancePage.tsx` | 5 | A-025, A-026, A-028, A-029, (route: A-027, A-030) |
| `frontend/src/pages/ConfigPage.tsx` | 3 | A-031, A-032, A-033 |

### Routes

| location | issueCount | issue IDs |
|---|---|---|
| `/` (index → redirect to `/fleet`) | 0 | — (examined: pure `<Navigate>` redirect, no rendered UI) |
| `/fleet` (Fleet Overview) | 2 | A-016, A-018 |
| `/live` (Live Monitor) | 2 | A-020, A-021 |
| `/alerts` (Alerts & Maintenance) | 2 | A-027, A-030 |
| `/config` (Local Config) | 0 | — (route-level: examined; endpoint exposure here is correct per Req 7.8; file-level issues tracked under `ConfigPage.tsx`) |

> Issues are listed under exactly one location. Issues whose root cause is a rendered-route behavior
> (endpoint exposure, connection-state treatment, error/retry handling) use the **route name** as
> their location; issues rooted in a specific source artifact use the **file path**.

## Summary

- **Total issues:** 35 (`A-001`–`A-035`).
- **By severity:** 4 critical (A-004, A-011, A-015, A-025), 17 major, 14 minor.
- **By category:** visual-design 4, layout-responsiveness 2, navigation-ia 2, accessibility 16,
  data-state-feedback 11.
- **Accessibility WCAG criteria referenced:** 1.1.1, 1.4.1, 1.4.3, 1.4.11, 2.3.3, 2.4.1, 2.4.2,
  2.4.7, 2.5.5, 3.3.1, 4.1.3.
- **Mandated findings recorded:** missing design tokens in `index.css` (A-001), non-collapsible nav
  on Mobile (A-011), and each color-only Status_Indicator instance (A-015 fleet status, A-025 alert
  severity, A-026 maintenance status).
- **Coverage:** all 12 source files plus the index redirect and the four routes were examined;
  zero-issue files/routes (`main.tsx`, `vite-env.d.ts`, `lib/api.ts`, `lib/ws.ts`,
  `lib/localConfig.ts`, `/`, `/config` route-level) are recorded explicitly.
