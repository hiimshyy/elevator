# Implementation Plan: UI/UX Responsive Redesign

## Overview

This plan implements the audit-first, plan-second, implement-third sequencing from the design. Stage 1 produces the `audit.md` deliverable, Stage 2 produces the approved `redesign-plan.md` deliverable, and Stage 3 implements the token foundations, theme system, navigation shell, responsive layout, accessibility hardening, and per-route redesign in the `frontend/` React + TypeScript codebase.

Production UI code changes in Stage 3 are gated behind the approval recorded in `redesign-plan.md` (Requirement 2.5). All code is TypeScript. Property-based tests use **fast-check** with Vitest + `@testing-library/react` + `jsdom`, and automated accessibility checks use `jest-axe`, as defined in the design's Testing Strategy. Each test sub-task is optional (marked `*`) and can be skipped for a faster MVP, but core implementation tasks must be completed.

## Tasks

- [x] 1. Produce the UI/UX Audit deliverable
  - Examine every source file and route under `frontend/src/` (`App.tsx`, `index.css`, `lib/*`, all four `pages/*`, `components/charts/*`, `components/layout/*`).
  - Create `.kiro/specs/ui-ux-responsive-redesign/audit.md` recording each issue with a stable unique ID, source location (file path or route name), exactly one severity (critical/major/minor), and exactly one category (visual-design / layout-responsiveness / navigation-ia / accessibility / data-state-feedback).
  - For accessibility-category issues, reference the specific WCAG 2.1 AA success criterion violated.
  - Explicitly record: missing Design_Token definitions in `index.css`, the non-collapsible nav on Mobile, and each color-only Status_Indicator instance.
  - Include a coverage list of all examined files/routes, recording examined-with-zero-issues entries where applicable.
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 1.10_

- [x] 2. Produce the approved Redesign Plan deliverable
  - Create `.kiro/specs/ui-ux-responsive-redesign/redesign-plan.md` listing each target component with a unique component ID and the existing source it replaces (or `net-new`).
  - Order implementation steps so Design_System token/component foundations precede route-level redesign steps; record `dependsOn` relationships.
  - Map each step to one or more Audit_Report issue IDs; for any step with no mapped issue, record an explicit justification.
  - Map every critical-severity audit issue to at least one planned step.
  - Record an approval decision (reviewer + ISO approval date). No Stage 3 production UI code changes proceed until this approval is recorded.
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7_

- [x] 3. Set up frontend test tooling
  - Add devDependencies to `frontend/package.json`: `vitest`, `@testing-library/react`, `@testing-library/user-event`, `jsdom`, `fast-check`, and `jest-axe` (plus types).
  - Add Vitest config (jsdom environment, setup file with `@testing-library/jest-dom` and `jest-axe` matchers) and a `test` script.
  - Verify the toolchain with a trivial smoke test that runs in single-run mode (no watch).
  - _Requirements: enables property-based and automated accessibility tests for Requirements 3, 4, 5, 6, 7, 8 (design Testing Strategy)_

- [x] 4. Implement the Design System token foundation
  - [x] 4.1 Create `frontend/src/styles/tokens.css`
    - Define CSS custom properties on `:root` for every category: color (incl. status colors + on-status text variants), typography (>= 5 font-size steps), spacing (>= 6 steps), border-radius, elevation, and motion.
    - Override the color and elevation tokens under `[data-theme="dark"]`; wrap motion tokens so they collapse to `0ms`/none under `prefers-reduced-motion`.
    - Import `tokens.css` ahead of existing styles.
    - _Requirements: 3.1, 3.2, 3.4, 3.5, 6.10_

  - [x] 4.2 Write property test for token resolution
    - **Property 1: Token resolution yields exactly one value per theme**
    - **Validates: Requirements 3.2**

  - [x] 4.3 Write token-usage enforcement test
    - Assert component styles reference `var(--token)` instead of hard-coded color/size literals, and assert all required token categories are present.
    - _Requirements: 3.1, 3.3, 3.4, 3.5_

- [x] 5. Implement the status-state mapping logic
  - [x] 5.1 Create the status-state mapper (`frontend/src/components/ui/statusState.ts`)
    - Define `StatusState` and `StatusVisual` (color token + distinct icon glyph + text label + shape) for healthy/warning/critical/unknown.
    - Implement domain-to-status mapping for elevator status/health score, alert severity, maintenance status, and connection state per the design's mapping table.
    - _Requirements: 3.6, 3.7, 6.3_

  - [x] 5.2 Write property test for status-indicator distinctness
    - **Property 2: Status indicators are distinct by a non-color attribute**
    - **Validates: Requirements 3.6, 3.7, 6.3**

- [x] 6. Implement the theme system
  - [x] 6.1 Create the ThemeProvider and theme controls (`frontend/src/theme/`)
    - Implement `resolveInitialTheme()` (stored preference -> OS `prefers-color-scheme` -> light default), `ThemeProvider`, and `useTheme()` applying `data-theme` to `document.documentElement`.
    - `setTheme` persists to `localStorage` key `elevator-pdm.theme`; on failure set `persistenceFailed` and keep the theme for the session. Switching applies within 500ms with no reload.
    - Add a `ThemeToggle` control.
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7_

  - [x] 6.2 Write property test for theme resolution precedence
    - **Property 15: Theme resolution follows stored-then-system-then-default precedence**
    - **Validates: Requirements 8.2, 8.3, 8.4**

  - [x] 6.3 Write property test for theme persistence round-trip
    - **Property 16: Theme persistence round-trips**
    - **Validates: Requirements 8.6**

  - [x] 6.4 Write unit tests for theme persistence failure
    - Verify a `localStorage` write failure keeps the theme applied and surfaces a non-blocking message.
    - _Requirements: 8.7_

- [x] 7. Implement the breakpoint classifier and hook
  - [x] 7.1 Create the layout classifier and `useBreakpoint` (`frontend/src/hooks/useBreakpoint.ts`)
    - Implement a pure `classifyWidth(width)` returning the Breakpoint plus a layout descriptor (column count, nav mode, content cap, horizontal-scroll flag) for sub-320 / Mobile / Tablet / Desktop / Large_Desktop bands.
    - Wrap it in `useBreakpoint()` using `window.matchMedia` listeners at the 640/1024/1440 thresholds.
    - _Requirements: 4.1, 4.2, 4.3, 4.5, 4.6, 4.8, 5.1, 5.2_

  - [x] 7.2 Write property test for breakpoint classification
    - **Property 3: Breakpoint classification is correct and stable within bands**
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.5, 4.6, 4.8, 5.1, 5.2**

- [x] 8. Implement the live-region announcer
  - [x] 8.1 Create `LiveRegionProvider` and `useAnnouncer` (`frontend/src/a11y/`)
    - Render persistent `aria-live="polite"` and `aria-live="assertive"` nodes near the root; expose `announcePolite`/`announceAssertive`.
    - _Requirements: 6.6, 6.7_

  - [x] 8.2 Write unit tests for announcer
    - Verify loading announces politely and error announces assertively with the message text.
    - _Requirements: 6.6, 6.7_

- [x] 9. Implement reusable UI primitives
  - [x] 9.1 Implement `Button` (`frontend/src/components/ui/Button.tsx`)
    - Variants primary/secondary/ghost, token-driven, visible focus ring, min 44x44px hit area.
    - _Requirements: 3.8, 6.4, 6.5_

  - [x] 9.2 Implement `Field` + `TextInput`/`Select`/`Textarea` (`frontend/src/components/ui/Field.tsx`)
    - Label association, `aria-describedby` wiring to validation messages exposing full text, 44px targets.
    - _Requirements: 3.8, 6.5, 6.8_

  - [x] 9.3 Implement `Card` (`frontend/src/components/ui/Card.tsx`)
    - Token-driven surface/elevation replacing `.card`/`.fleet-card`/`.summary-card`/`.panel`/`.workflow-card`.
    - _Requirements: 3.8_

  - [x] 9.4 Implement `StatusBadge` (`frontend/src/components/ui/StatusBadge.tsx`)
    - Render color + icon + label + shape from the status-state mapper for each state.
    - _Requirements: 3.6, 3.7, 3.8, 6.3_

  - [x] 9.5 Implement `DataState` (`frontend/src/components/ui/DataState.tsx`)
    - Loading (spinner + polite announce), empty (names missing data), and error (view name + reason + retry control) presentations, integrating `useAnnouncer`.
    - _Requirements: 3.8, 7.1, 7.3, 7.4_

  - [x] 9.6 Write property test for touch-target size
    - **Property 7: Interactive controls meet the minimum touch-target size**
    - **Validates: Requirements 6.5**

  - [x] 9.7 Write property test for validation message linkage
    - **Property 8: Validation messages are accessibly linked with full text**
    - **Validates: Requirements 6.8**

- [x] 10. Implement palette contrast verification logic
  - [x] 10.1 Create the contrast utility and token-pairing map (`frontend/src/a11y/contrast.ts`)
    - Implement WCAG relative-luminance contrast computation and enumerate the actual foreground/background token pairings used together per theme (normal text, large text, status graphical elements, focus-indicator vs adjacent).
    - _Requirements: 6.1, 6.2, 6.4, 8.8_

  - [x] 10.2 Write property test for palette contrast
    - **Property 6: Palette contrast meets WCAG AA in every theme**
    - **Validates: Requirements 6.1, 6.2, 6.4, 8.8**

- [x] 11. Checkpoint - foundations
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 12. Implement the Navigation Shell
  - [ ] 12.1 Create `NavigationShell` and nav toggle reducer (`frontend/src/components/layout/NavigationShell.tsx`)
    - Persistent sidebar at Desktop/Large_Desktop; collapsed-behind-menu-control at Mobile/Tablet with a toggle that flips expanded/collapsed and a link-selection action that navigates then collapses.
    - Apply an active-link treatment using `aria-current="page"` plus a non-color distinction (rail indicator/weight); include a skip-to-content link and the `ThemeToggle`. Remove endpoint URL/status from the sidebar brand block.
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 7.8_

  - [ ] 12.2 Write property test for navigation toggle
    - **Property 4: Navigation toggle is an involution and link selection collapses**
    - **Validates: Requirements 5.3, 5.4, 5.5**

  - [ ] 12.3 Write property test for active navigation link distinction
    - **Property 5: Active navigation link is distinguished by a non-color means**
    - **Validates: Requirements 5.7**

- [ ] 13. Implement the responsive layout container
  - [ ] 13.1 Create `PageContainer`/`ResponsiveLayout` (`frontend/src/components/layout/PageContainer.tsx`)
    - Single-column at Mobile, <= 2 columns at Tablet, content capped at 1440px and centered at Large_Desktop; no horizontal page scroll at >= 320px, single column with horizontal scroll permitted below 320px. Consume `useBreakpoint`.
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.6, 4.7, 4.8_

  - [ ] 13.2 Write integration tests for responsive layout
    - Verify column count and content-cap changes occur only at defined thresholds using simulated viewport widths.
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.6, 4.8_

- [ ] 14. Implement data-state handling
  - [ ] 14.1 Create the view data-state reducer and request lifecycle (`frontend/src/lib/viewState.ts`)
    - Implement `ViewDataState<T>` transitions (loading/empty/error/populated) holding `data` and `error` separately; wire loading indicator within 300ms, a 30s `AbortController` watchdog producing a timeout error with retry, error messages containing view name + reason while preserving prior data, and retry returning to loading.
    - _Requirements: 7.1, 7.2, 7.4, 7.5_

  - [ ] 14.2 Write property test for empty-state naming
    - **Property 10: Empty state names the missing data**
    - **Validates: Requirements 7.3**

  - [ ] 14.3 Write property test for error-state data preservation
    - **Property 11: Error state preserves prior data and describes the failure**
    - **Validates: Requirements 7.4**

  - [ ] 14.4 Write unit tests for data-state timing
    - Use fake timers to verify the 300ms loading indicator and 30s timeout-to-error transition.
    - _Requirements: 7.1, 7.2, 7.5_

- [ ] 15. Redesign the Fleet Overview route
  - [ ] 15.1 Refactor `frontend/src/pages/FleetOverviewPage.tsx`
    - Replace literal-styled markup with `Card`/`StatusBadge`/`Button`/`DataState` primitives inside `PageContainer`; remove any endpoint URL strings.
    - _Requirements: 3.3, 3.8, 4.1, 4.2, 6.3, 7.1, 7.3, 7.4, 7.8_

- [ ] 16. Redesign the Live Monitor route
  - [ ] 16.1 Refactor `frontend/src/pages/LiveMonitorPage.tsx` and `frontend/src/components/charts/MetricSparkline.tsx`
    - Single-column charts at Mobile; give `MetricSparkline` an accessible text alternative including latest value, unit, and timestamp; render a persistent synthetic-trace label; normalize WebSocket state to three mutually distinct connection treatments updated within 1s. Remove endpoint URL strings.
    - _Requirements: 4.5, 6.9, 7.6, 7.7, 7.8_

  - [ ] 16.2 Write property test for chart text alternative
    - **Property 9: Chart text alternative includes latest value, unit, and timestamp**
    - **Validates: Requirements 6.9**

  - [ ] 16.3 Write property test for synthetic-trace labeling
    - **Property 12: Synthetic telemetry is always labeled when present**
    - **Validates: Requirements 7.6**

  - [ ] 16.4 Write property test for connection-state treatments
    - **Property 13: Connection states map to three mutually distinct treatments**
    - **Validates: Requirements 7.7**

- [ ] 17. Redesign the Alerts & Maintenance route
  - [ ] 17.1 Refactor `frontend/src/pages/AlertsMaintenancePage.tsx`
    - Replace literal-styled markup with primitives inside `PageContainer`; use `StatusBadge` for alert severity and maintenance status; remove endpoint URL strings.
    - _Requirements: 3.3, 3.8, 4.1, 4.2, 6.3, 7.1, 7.3, 7.4, 7.8_

- [ ] 18. Redesign the Local Config route
  - [ ] 18.1 Refactor `frontend/src/pages/ConfigPage.tsx`
    - Use `Field`/`Button` primitives with `aria-describedby` validation messaging inside `PageContainer`; keep internal endpoint URLs presented here only.
    - _Requirements: 3.3, 3.8, 6.8, 7.8_

  - [ ] 18.2 Write property test for endpoint-URL confinement
    - **Property 14: Endpoint URLs are confined to the Local Config route**
    - **Validates: Requirements 7.8**

- [ ] 19. Harden global accessibility behavior
  - [ ] 19.1 Apply focus, keyboard, and reduced-motion treatments
    - Add token-driven visible focus indicators (>= 3:1), ensure full keyboard operability with no focus traps across all interactive elements, and disable non-essential animation under `prefers-reduced-motion`.
    - _Requirements: 6.4, 6.10, 6.11, 6.12_

  - [ ] 19.2 Write automated accessibility tests per route
    - Run `jest-axe` against each of the four redesigned routes and assert no violations.
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.11, 6.12_

- [ ] 20. Integrate and wire the application shell
  - [ ] 20.1 Wire providers and shell into `frontend/src/App.tsx` and `frontend/src/main.tsx`
    - Mount `ThemeProvider` and `LiveRegionProvider` at the root, replace `AppShell` with `NavigationShell`, and route the four pages through `PageContainer`.
    - _Requirements: 5.1, 5.2, 8.1, 8.5_

  - [ ] 20.2 Write integration test for cross-route theme switching
    - Verify selecting a theme applies to all four routes within the budget without a reload.
    - _Requirements: 8.5_

- [ ] 21. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional test sub-tasks and can be skipped for a faster MVP.
- Each task references specific requirements for traceability; each property test references its design property number.
- Stage 3 (tasks 4+) must not change production UI behavior until the approval in `redesign-plan.md` is recorded (Requirement 2.5).
- Property tests use fast-check with a minimum of 100 iterations and are tagged `// Feature: ui-ux-responsive-redesign, Property {number}: {property_text}` per the design Testing Strategy.
- Each correctness property maps to exactly one property-based test sub-task.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "3.1"] },
    { "id": 1, "tasks": ["2.1"] },
    { "id": 2, "tasks": ["4.1", "5.1", "6.1", "7.1", "8.1"] },
    { "id": 3, "tasks": ["4.2", "4.3", "5.2", "6.2", "6.3", "6.4", "7.2", "8.2", "10.1", "9.1", "9.2", "9.3", "9.4", "9.5", "12.1", "13.1", "14.1"] },
    { "id": 4, "tasks": ["9.6", "9.7", "10.2", "12.2", "12.3", "13.2", "14.2", "14.3", "14.4", "15.1", "16.1", "17.1", "18.1", "20.1"] },
    { "id": 5, "tasks": ["16.2", "16.3", "16.4", "18.2", "20.2", "19.1"] },
    { "id": 6, "tasks": ["19.2"] }
  ]
}
```
