# Redesign Plan — Elevator PDM Operations Console (`frontend/`)

Stage 2 deliverable for the `ui-ux-responsive-redesign` spec. This document defines the target
component inventory, a dependency-ordered sequence of implementation steps, and maps every step to
one or more issues from `audit.md`. It is produced and approved **before** any production UI code
changes (plan-second sequencing, Requirement 2.5).

---

## Approval Decision (Requirement 2.6)

| Field | Value |
|---|---|
| **Reviewer** | Weerayut Inthamorn (Engineering Lead) |
| **Approved date** | 2025-07-16 |
| **Decision** | Approved — Stage 3 implementation may proceed |

> All Stage 3 production UI code changes (tasks 3 onward) are gated on this approval record.
> No redesign code was committed before this date.

---

## Component Inventory (Requirement 2.1)

Each target component is assigned a unique component ID and references the existing source file or
markup it replaces, or is designated `net-new` where it replaces nothing.

| Component ID | Target Component | Replaces |
|---|---|---|
| **C-01** | `frontend/src/styles/tokens.css` | Hard-coded literals in `frontend/src/index.css` (no token system) |
| **C-02** | `frontend/src/theme/ThemeProvider.tsx` | `net-new` (no theme system exists) |
| **C-03** | `frontend/src/theme/ThemeToggle.tsx` | `net-new` |
| **C-04** | `frontend/src/hooks/useBreakpoint.ts` | Ad-hoc `@media (max-width:960px)` / `max-width:720px` rules in `index.css` |
| **C-05** | `frontend/src/components/ui/statusState.ts` | Inline `getStatusTone()` / `getAlertTone()` / `getMaintenanceTone()` functions in `FleetOverviewPage.tsx` and `AlertsMaintenancePage.tsx` |
| **C-06** | `frontend/src/components/ui/Button.tsx` | `.button-link`, `.action-button`, `.action-button--danger` literal styles in `index.css` |
| **C-07** | `frontend/src/components/ui/Field.tsx` (+ `TextInput`, `Select`, `Textarea`) | Bare `<input>`, `<select>`, `<textarea>` with ad-hoc `.form-group`/`.form-control` classes in `AlertsMaintenancePage.tsx` and `ConfigPage.tsx` |
| **C-08** | `frontend/src/components/ui/Card.tsx` | `.card`, `.fleet-card`, `.summary-card`, `.panel`, `.workflow-card` literal styles in `index.css` |
| **C-09** | `frontend/src/components/ui/StatusBadge.tsx` | `.status-badge--healthy/--warning/--critical` in `index.css` and their usages in `FleetOverviewPage.tsx`, `AlertsMaintenancePage.tsx` |
| **C-10** | `frontend/src/components/ui/DataState.tsx` | Inline loading/error/empty JSX in each of the four pages |
| **C-11** | `frontend/src/a11y/LiveRegionProvider.tsx` (+ `useAnnouncer`) | `net-new` (no live-region infrastructure exists) |
| **C-12** | `frontend/src/a11y/contrast.ts` | `net-new` (no contrast utility exists) |
| **C-13** | `frontend/src/components/layout/NavigationShell.tsx` | `frontend/src/components/layout/AppShell.tsx` |
| **C-14** | `frontend/src/components/layout/PageContainer.tsx` | Ad-hoc `.content`, `.grid--2`, `.grid--3` column rules in `index.css` |
| **C-15** | `frontend/src/lib/viewState.ts` | Inline `isLoading`/`error`/`elevators` state pairs scattered across each page |
| **C-16** | `frontend/src/pages/FleetOverviewPage.tsx` (refactored) | `frontend/src/pages/FleetOverviewPage.tsx` (current) |
| **C-17** | `frontend/src/pages/LiveMonitorPage.tsx` (refactored) | `frontend/src/pages/LiveMonitorPage.tsx` (current) |
| **C-18** | `frontend/src/components/charts/MetricSparkline.tsx` (refactored) | `frontend/src/components/charts/MetricSparkline.tsx` (current) |
| **C-19** | `frontend/src/pages/AlertsMaintenancePage.tsx` (refactored) | `frontend/src/pages/AlertsMaintenancePage.tsx` (current) |
| **C-20** | `frontend/src/pages/ConfigPage.tsx` (refactored) | `frontend/src/pages/ConfigPage.tsx` (current) |
| **C-21** | `frontend/src/App.tsx` (refactored) | `frontend/src/App.tsx` (current) |
| **C-22** | `frontend/src/main.tsx` (refactored) | `frontend/src/main.tsx` (current) |

---

## Implementation Steps (Requirements 2.2, 2.3, 2.4, 2.7)

Steps are ordered so Design_System token/component foundations precede route-level redesign steps.
`dependsOn` lists the step IDs that must be complete before a step begins.

---

### Stage 3-A — Test tooling

#### S-01 · Set up frontend test tooling

- **components:** (build infrastructure, no component ID)
- **dependsOn:** *(none — may proceed as soon as approval is recorded)*
- **mappedIssueIds:** *(none)*
- **justification:** No audit issue requires test tooling itself, but the testing strategy in
  `design.md` mandates Vitest + fast-check + `@testing-library/react` + `jest-axe` for all
  property-based and accessibility verification tests in subsequent steps. This step is a prerequisite
  for every test sub-task that validates a correctness property or accessibility requirement.

---

### Stage 3-B — Design System foundations

These steps must precede any route-level implementation.

#### S-02 · Introduce Design Token CSS custom properties (`tokens.css`)

- **components:** C-01
- **dependsOn:** S-01
- **mappedIssueIds:** A-001, A-002, A-003, A-005, A-008, A-035
- **description:** Create `frontend/src/styles/tokens.css` defining CSS custom properties on `:root`
  for color (including status colors and on-status text variants), typography (≥5 font-size steps),
  spacing (≥6 steps), border-radius, elevation, and motion. Override color/elevation tokens under
  `[data-theme="dark"]`. Wrap motion tokens so they collapse to `0ms`/none under
  `prefers-reduced-motion: reduce`. Import `tokens.css` ahead of existing styles in `index.css`.
  Replace all hard-coded literal values in `index.css` with `var(--token)` references.

#### S-03 · Implement the status-state mapper

- **components:** C-05
- **dependsOn:** S-02
- **mappedIssueIds:** A-015, A-025, A-026
- **description:** Create `frontend/src/components/ui/statusState.ts` defining `StatusState`,
  `StatusVisual` (color token + distinct icon glyph + text label + shape), and the domain-to-status
  mapping for elevator status/health score, alert severity, maintenance status, and connection state.
  Replaces the inline `getStatusTone/getAlertTone/getMaintenanceTone` functions.

#### S-04 · Implement the ThemeProvider and ThemeToggle

- **components:** C-02, C-03
- **dependsOn:** S-02
- **mappedIssueIds:** A-002
- **description:** Create `frontend/src/theme/ThemeProvider.tsx` implementing `resolveInitialTheme()`
  (stored preference → OS `prefers-color-scheme` → light default), `ThemeProvider`, and `useTheme()`.
  Applies `data-theme` to `document.documentElement` and persists to `localStorage` key
  `elevator-pdm.theme`; on failure sets `persistenceFailed` and keeps the theme for the session.
  Create `ThemeToggle` control.

#### S-05 · Implement the breakpoint classifier and `useBreakpoint` hook

- **components:** C-04
- **dependsOn:** S-02
- **mappedIssueIds:** A-006, A-007, A-011
- **description:** Create `frontend/src/hooks/useBreakpoint.ts` implementing a pure `classifyWidth(w)`
  returning Breakpoint + layout descriptor (column count, nav mode, content cap, horizontal-scroll
  flag) for sub-320 / Mobile / Tablet / Desktop / Large_Desktop bands. Wrap in `useBreakpoint()`
  using `window.matchMedia` listeners at 640 / 1024 / 1440 thresholds.

#### S-06 · Implement the live-region announcer

- **components:** C-11
- **dependsOn:** S-02
- **mappedIssueIds:** A-017, A-024, A-030, A-031
- **description:** Create `frontend/src/a11y/LiveRegionProvider.tsx` rendering persistent
  `aria-live="polite"` and `aria-live="assertive"` nodes near the root. Expose `useAnnouncer()` for
  `announcePolite` and `announceAssertive`. Any view can call these to satisfy the 1-second
  announcement budget for loading and error state changes.

#### S-07 · Implement reusable UI primitives (Button, Field, Card, StatusBadge, DataState)

- **components:** C-06, C-07, C-08, C-09, C-10
- **dependsOn:** S-02, S-03, S-06
- **mappedIssueIds:** A-003, A-004, A-005, A-015, A-017, A-018, A-019, A-024, A-025, A-026, A-028, A-029, A-030, A-031, A-032, A-034
- **description:**
  - **`Button`** — primary/secondary/ghost variants, token-driven, min 44×44px hit area, visible
    `:focus-visible` ring at ≥3:1 contrast. Replaces `.button-link`/`.action-button*` literals.
  - **`Field` + `TextInput`/`Select`/`Textarea`** — label association, `aria-describedby` wiring to
    validation messages exposing full text, `aria-invalid`, 44px hit targets. Replaces bare inputs
    with ad-hoc form classes.
  - **`Card`** — token-driven surface/elevation. Replaces `.card`/`.fleet-card`/`.summary-card`/
    `.panel`/`.workflow-card`.
  - **`StatusBadge`** — renders color + distinct icon glyph + text label + shape from the
    status-state mapper. Each of the four states (healthy/warning/critical/unknown) differs from
    the others by a non-color attribute.
  - **`DataState`** — loading (spinner + polite announce), empty (names missing data), and error
    (view name + reason + retry control) presentations using `useAnnouncer`.

#### S-08 · Implement palette contrast verification utility

- **components:** C-12
- **dependsOn:** S-02
- **mappedIssueIds:** A-003, A-005
- **description:** Create `frontend/src/a11y/contrast.ts` implementing WCAG relative-luminance
  contrast computation and enumerating the actual foreground/background token pairings used together
  per theme (normal text, large text, status graphical elements, focus-indicator vs adjacent).
  Used by the Property 6 property-based test to verify all palette pairs meet AA thresholds.

---

### Stage 3-C — Navigation shell and layout container

These steps depend on the Design System foundations (S-02 through S-07).

#### S-09 · Implement the NavigationShell

- **components:** C-13
- **dependsOn:** S-02, S-04, S-05
- **mappedIssueIds:** A-011, A-012, A-013, A-014
- **description:** Create `frontend/src/components/layout/NavigationShell.tsx` replacing
  `AppShell.tsx`. Persistent sidebar at Desktop/Large_Desktop; collapsed behind a single menu
  control at Mobile/Tablet. Toggle flips expanded/collapsed; link selection navigates then collapses.
  Active link uses `aria-current="page"` plus a non-color distinction (left rail indicator +
  weight) distinct from hover. Includes a skip-to-content link and `ThemeToggle`. Removes endpoint
  URL/status from the brand block.

#### S-10 · Implement the responsive layout container (PageContainer)

- **components:** C-14
- **dependsOn:** S-02, S-05
- **mappedIssueIds:** A-006, A-007
- **description:** Create `frontend/src/components/layout/PageContainer.tsx`. Single column at
  Mobile, ≤2 columns at Tablet, content capped at 1440px and centered at Large_Desktop; no
  horizontal page scroll at ≥320px; single column with horizontal scroll permitted below 320px.
  Consumes `useBreakpoint`.

---

### Stage 3-D — Data-state handling

#### S-11 · Implement the view data-state reducer and request lifecycle

- **components:** C-15
- **dependsOn:** S-06, S-07
- **mappedIssueIds:** A-018, A-019, A-030
- **description:** Create `frontend/src/lib/viewState.ts` implementing `ViewDataState<T>`
  transitions (loading/empty/error/populated), holding `data` and `error` separately. Wire loading
  indicator within 300ms, a 30s `AbortController` watchdog producing a timeout error with retry,
  error messages containing view name + reason while preserving prior data, and retry returning to
  loading.

---

### Stage 3-E — Route-level redesign

Route steps depend on all foundations and shell steps.

#### S-12 · Redesign the Fleet Overview route

- **components:** C-16
- **dependsOn:** S-07, S-09, S-10, S-11
- **mappedIssueIds:** A-015, A-016, A-017, A-018, A-019
- **description:** Refactor `FleetOverviewPage.tsx`. Replace literal-styled markup with
  `Card`/`StatusBadge`/`Button`/`DataState` primitives inside `PageContainer`. Remove endpoint URL
  strings. Use `DataState` for loading/empty/error with `useAnnouncer` integration.

#### S-13 · Redesign the Live Monitor route and MetricSparkline

- **components:** C-17, C-18
- **dependsOn:** S-07, S-09, S-10, S-11
- **mappedIssueIds:** A-020, A-021, A-022, A-023, A-024, A-034, A-035
- **description:** Refactor `LiveMonitorPage.tsx` and `MetricSparkline.tsx`. Single-column charts at
  Mobile. Give `MetricSparkline` an accessible text alternative including latest value, unit, and
  timestamp. Render a persistent synthetic-trace label. Normalize WebSocket state to three mutually
  distinct connection treatments updated within 1s. Wrap `JSON.parse` in try/catch. Remove endpoint
  URL strings. Drive chart colors from tokens.

#### S-14 · Redesign the Alerts & Maintenance route

- **components:** C-19
- **dependsOn:** S-07, S-09, S-10, S-11
- **mappedIssueIds:** A-025, A-026, A-027, A-028, A-029, A-030
- **description:** Refactor `AlertsMaintenancePage.tsx`. Replace literal-styled markup with
  `Card`/`StatusBadge`/`Field`/`Button`/`DataState` primitives inside `PageContainer`. Use
  `StatusBadge` for alert severity (with correct critical→critical mapping) and maintenance status.
  Wire `aria-describedby`/`aria-invalid` on form fields. Expand checkbox hit area to 44×44px. Remove
  endpoint URL strings.

#### S-15 · Redesign the Local Config route

- **components:** C-20
- **dependsOn:** S-07, S-09, S-10
- **mappedIssueIds:** A-031, A-032, A-033
- **description:** Refactor `ConfigPage.tsx` using `Field`/`Button` primitives with
  `aria-describedby` validation messaging inside `PageContainer`. Route save/test feedback through
  polite/assertive live regions via `useAnnouncer`. Mask the API key field (with reveal toggle) and
  avoid printing the literal default key. Keep internal endpoint URLs here only (correct per
  Requirement 7.8).

---

### Stage 3-F — Accessibility hardening and application wiring

#### S-16 · Apply global focus, keyboard, and reduced-motion treatments

- **components:** (cross-cutting style/behavior, no single component ID)
- **dependsOn:** S-02, S-07, S-09, S-12, S-13, S-14, S-15
- **mappedIssueIds:** A-004, A-008, A-009
- **description:** Add token-driven visible focus indicators (≥3:1) across all interactive elements.
  Ensure full keyboard operability with no focus traps. Set route-specific `document.title` per
  route. Disable non-essential animation under `prefers-reduced-motion: reduce` via motion tokens.

#### S-17 · Wire providers and shell into App.tsx and main.tsx

- **components:** C-21, C-22
- **dependsOn:** S-04, S-06, S-09, S-10
- **mappedIssueIds:** A-010, A-011, A-013
- **description:** Mount `ThemeProvider` and `LiveRegionProvider` at the root in `main.tsx`.
  Replace `AppShell` with `NavigationShell` in `App.tsx`. Route the four pages through
  `PageContainer`. Add a top-level React error boundary for A-010.

---

## Critical Issue Coverage (Requirement 2.7)

All four critical-severity issues are mapped to at least one implementation step.

| Issue ID | Severity | Description | Mapped Steps |
|---|---|---|---|
| **A-004** | critical | No visible focus indicator (`index.css`) | S-07 (Button/Field primitives add focus ring), S-16 (global focus treatment) |
| **A-011** | critical | Navigation does not collapse on Mobile/Tablet (`AppShell.tsx`) | S-05 (breakpoint hook), S-09 (NavigationShell), S-17 (wired into App) |
| **A-015** | critical | Color-only elevator status indicator (`FleetOverviewPage.tsx`) | S-03 (status mapper), S-07 (StatusBadge), S-12 (Fleet route refactor) |
| **A-025** | critical | Color-only (and misleading) alert severity indicator (`AlertsMaintenancePage.tsx`) | S-03 (status mapper), S-07 (StatusBadge), S-14 (Alerts route refactor) |

---

## Full Issue-to-Step Mapping (Requirement 2.3)

| Issue ID | Severity | Mapped Step(s) |
|---|---|---|
| A-001 | major | S-02 |
| A-002 | major | S-02, S-04 |
| A-003 | major | S-02, S-07, S-08 |
| A-004 | **critical** | S-07, S-16 |
| A-005 | minor | S-02, S-07, S-08 |
| A-006 | major | S-05, S-10 |
| A-007 | minor | S-05, S-10 |
| A-008 | minor | S-02, S-16 |
| A-009 | minor | S-16 |
| A-010 | minor | S-17 |
| A-011 | **critical** | S-05, S-09, S-17 |
| A-012 | major | S-09 |
| A-013 | major | S-09, S-17 |
| A-014 | minor | S-09 |
| A-015 | **critical** | S-03, S-07, S-12 |
| A-016 | major | S-12 |
| A-017 | major | S-06, S-07, S-12 |
| A-018 | major | S-07, S-11, S-12 |
| A-019 | minor | S-07, S-11, S-12 |
| A-020 | major | S-13 |
| A-021 | major | S-13 |
| A-022 | minor | S-13 |
| A-023 | minor | S-13 |
| A-024 | minor | S-06, S-13 |
| A-025 | **critical** | S-03, S-07, S-14 |
| A-026 | major | S-03, S-07, S-14 |
| A-027 | major | S-14 |
| A-028 | major | S-07, S-14 |
| A-029 | minor | S-07, S-14 |
| A-030 | minor | S-06, S-07, S-11, S-14 |
| A-031 | major | S-06, S-15 |
| A-032 | major | S-07, S-15 |
| A-033 | minor | S-15 |
| A-034 | major | S-07, S-13 |
| A-035 | minor | S-02, S-13 |

> All 35 audit issues (A-001 through A-035) are mapped to at least one step.
> All four critical-severity issues are mapped to at least one step (Requirement 2.7).
> No step is left without either a mapped issue or an explicit justification (Requirement 2.4).

---

## Step Dependency Graph

```
S-01 (test tooling)
└── S-02 (tokens.css)
    ├── S-03 (status mapper)
    ├── S-04 (ThemeProvider)
    ├── S-05 (useBreakpoint)
    ├── S-06 (LiveRegionProvider)
    ├── S-07 (UI primitives) ← also depends on S-03, S-06
    ├── S-08 (contrast utility)
    ├── S-09 (NavigationShell) ← also depends on S-04, S-05
    ├── S-10 (PageContainer)   ← also depends on S-05
    └── S-11 (viewState.ts)    ← also depends on S-06, S-07
        ├── S-12 (Fleet route)   ← also depends on S-07, S-09, S-10
        ├── S-13 (Live route)    ← also depends on S-07, S-09, S-10
        ├── S-14 (Alerts route)  ← also depends on S-07, S-09, S-10
        └── S-15 (Config route)  ← also depends on S-07, S-09, S-10 (not S-11)
            └── S-16 (a11y hardening) ← also depends on S-02, S-07, S-09, S-12–S-15
                └── S-17 (App/main wiring) ← also depends on S-04, S-06, S-09, S-10
```

