# Requirements Document

## Introduction

This feature covers a UI/UX quality and responsive-design redesign of the Elevator Predictive Maintenance (PDM) operations console located in `frontend/` (React + TypeScript + Vite). The current frontend is functional but ships as four routed pages (Fleet Overview, Live Monitor, Alerts & Maintenance, Local Config) styled by a single hand-written global stylesheet with no design tokens, no theming, color-only status signaling, a non-collapsible sidebar, and limited accessibility support.

Per the explicit request, this work is sequenced as **audit first, plan second, implement third**. The requirements below therefore treat the documented UI/UX audit and the approved redesign plan as first-class deliverables that MUST be produced and reviewed before any production UI code is changed. The requirements also define the target design system, responsive behavior, accessibility conformance, and UX improvements that the eventual implementation must satisfy.

The scope is limited to the presentation layer in `frontend/`. The REST history contract and live WebSocket telemetry contract served by FastAPI are treated as fixed inputs; this redesign does not change backend API shapes.

## Glossary

- **Operations_Console**: The complete redesigned React frontend application served from `frontend/`, comprising all routes, layout, and components.
- **Audit_Report**: A written deliverable that enumerates the UI/UX issues found in the current `frontend/` implementation, each with a location, severity, and recommended direction.
- **Redesign_Plan**: A written deliverable that defines the proposed target design, component inventory, and a phased, dependency-ordered sequence of implementation steps, produced and approved before production UI code changes.
- **Design_System**: The shared set of design tokens (color, typography, spacing, radius, elevation, motion), reusable UI components, and usage rules consumed by the Operations_Console.
- **Design_Token**: A named, single-source-of-truth value (for example a color, spacing step, or font size) referenced by components rather than a hard-coded literal.
- **Responsive_Layout**: The layout system of the Operations_Console that adapts content arrangement to the active viewport breakpoint.
- **Navigation_Shell**: The application chrome that provides primary navigation between routes, including the sidebar on large viewports and the collapsible menu on small viewports.
- **Status_Indicator**: Any UI element that communicates a state or severity (for example elevator status, alert severity, connection state, maintenance status).
- **Data_State**: The presentation condition of a data-driven view, one of: loading, empty, error, or populated.
- **Live_Telemetry_View**: The Live Monitor view that renders historical readings and live WebSocket packets, including any interpolated (synthetic) trace.
- **Breakpoint**: A defined viewport-width threshold at which the Responsive_Layout changes arrangement. Defined breakpoints are: Mobile (viewport width below 640px), Tablet (640px to 1023px inclusive), Desktop (1024px to 1439px inclusive), and Large_Desktop (1440px and above).
- **WCAG_AA**: Web Content Accessibility Guidelines version 2.1, conformance level AA.
- **Touch_Target**: An interactive control activated by pointer or touch input.

## Requirements

### Requirement 1: UI/UX Audit of the Existing Frontend

**User Story:** As a product owner, I want a documented audit of the current frontend before any redesign work, so that redesign decisions are grounded in identified, traceable issues rather than assumptions.

#### Acceptance Criteria

1. THE Audit_Report SHALL document each identified UI/UX issue with a source location expressed as a file path when the issue originates in a source file, or as a route name when the issue originates in a rendered route.
2. THE Audit_Report SHALL assign each identified issue exactly one severity value from the set: critical, major, or minor.
3. THE Audit_Report SHALL assign each identified issue exactly one category from the set: visual design, layout and responsiveness, navigation and information architecture, accessibility, or data-state and feedback handling.
4. THE Audit_Report SHALL record the absence of shared Design_Token definitions in each current stylesheet that lacks them as an identified issue.
5. THE Audit_Report SHALL record the non-collapsible Navigation_Shell behavior on Mobile viewports as an identified issue.
6. THE Audit_Report SHALL record each instance of color-only status signaling in the current Status_Indicator elements as an identified issue.
7. WHERE an identified issue is categorized as accessibility, THE Audit_Report SHALL reference the specific WCAG_AA success criterion that the issue violates.
8. THE Audit_Report SHALL assign each identified issue a unique identifier that remains constant across the report so that the issue is individually traceable.
9. THE Audit_Report SHALL document the set of source files and routes that were examined during the audit, so that audit coverage is verifiable.
10. IF an examined source file or route contains no identified issue, THEN THE Audit_Report SHALL record that source file or route as examined with zero issues.

### Requirement 2: Redesign Plan Before Implementation

**User Story:** As an engineering lead, I want an approved redesign plan before code changes, so that implementation proceeds in a reviewed, dependency-ordered sequence.

#### Acceptance Criteria

1. THE Redesign_Plan SHALL list each target UI component with a unique component identifier together with the existing component or markup, expressed as a file path or component name, that the target component replaces, or designate the target component as net-new where it replaces no existing component or markup.
2. THE Redesign_Plan SHALL order implementation steps so that Design_System token and component foundations precede route-level redesign steps.
3. THE Redesign_Plan SHALL map each planned implementation step to one or more identified issues from the Audit_Report.
4. IF an implementation step has no mapped issue from the Audit_Report, THEN THE Redesign_Plan SHALL record an explicit justification for that step.
5. WHILE the Redesign_Plan has no recorded approval decision, THE Operations_Console SHALL retain the current production UI behavior with no redesign code changes.
6. THE Redesign_Plan SHALL record an approval decision that identifies the approving reviewer and the approval date.
7. THE Redesign_Plan SHALL map each Audit_Report issue assigned a severity of critical to at least one planned implementation step.

### Requirement 3: Design System and Visual Language

**User Story:** As a frontend developer, I want a token-based design system, so that visual styling is consistent, themeable, and maintainable across all routes.

#### Acceptance Criteria

1. THE Design_System SHALL define at least one named Design_Token entry for each token category: color, typography, spacing, border-radius, elevation, and motion.
2. THE Design_System SHALL resolve each Design_Token to exactly one value per active theme.
3. THE Operations_Console SHALL reference Design_Token entries for color, typography, spacing, border-radius, elevation, and motion values instead of hard-coded literals in component styles.
4. THE Design_System SHALL define a typographic scale containing at least five named font-size steps.
5. THE Design_System SHALL define a spacing scale containing at least six named spacing steps.
6. THE Design_System SHALL define a named visual treatment for each Status_Indicator state: healthy, warning, critical, and unknown.
7. THE Design_System SHALL ensure each Status_Indicator state visual treatment differs from the other three states by a non-color attribute in addition to color.
8. THE Design_System SHALL provide reusable components for buttons, form fields, cards, status badges, and data-state messages.

### Requirement 4: Responsive Layout Across Devices

**User Story:** As an operations technician, I want the console to adapt to phones, tablets, and desktops, so that I can monitor elevators from any device without horizontal scrolling.

#### Acceptance Criteria

1. WHILE the viewport is at the Mobile breakpoint, THE Responsive_Layout SHALL arrange primary content in a single column.
2. WHILE the viewport is at the Tablet breakpoint, THE Responsive_Layout SHALL arrange multi-card content in at most two columns.
3. WHILE the viewport is at the Large_Desktop breakpoint, THE Responsive_Layout SHALL constrain the primary content region to a maximum width of 1440px and center the content region horizontally.
4. WHILE the viewport width is 320px or greater, THE Operations_Console SHALL present all content without requiring horizontal page scrolling.
5. WHILE the viewport is at the Mobile breakpoint, THE Live_Telemetry_View SHALL arrange metric charts in a single column.
6. THE Responsive_Layout SHALL change column count and content region width only when the viewport crosses a defined Breakpoint threshold.
7. WHEN the viewport crosses a defined Breakpoint threshold, THE Responsive_Layout SHALL complete the resulting layout reflow within 500 milliseconds.
8. IF the viewport width is less than 320px, THEN THE Operations_Console SHALL retain a single-column layout and permit horizontal page scrolling.

### Requirement 5: Responsive Navigation Shell

**User Story:** As a mobile user, I want navigation that collapses on small screens, so that screen space is reserved for monitoring content.

#### Acceptance Criteria

1. WHILE the viewport is at the Desktop breakpoint or the Large_Desktop breakpoint, THE Navigation_Shell SHALL display the primary navigation as a persistent sidebar.
2. WHILE the viewport is at the Mobile breakpoint or the Tablet breakpoint, THE Navigation_Shell SHALL collapse the primary navigation behind a single menu control.
3. WHEN a user activates the menu control while the primary navigation is collapsed, THE Navigation_Shell SHALL display the primary navigation links.
4. WHEN a user activates the menu control while the primary navigation is expanded, THE Navigation_Shell SHALL collapse the primary navigation.
5. WHEN a user selects a navigation link while the primary navigation is collapsed-capable, THE Navigation_Shell SHALL navigate to the selected route and collapse the primary navigation.
6. WHEN the viewport transitions to the Desktop breakpoint or the Large_Desktop breakpoint while the primary navigation is expanded, THE Navigation_Shell SHALL display the primary navigation as a persistent sidebar.
7. WHILE a route is active, THE Navigation_Shell SHALL apply a visual treatment to the navigation link for that route that is distinct from all non-active navigation links and that indicates the current route through a means in addition to color.

### Requirement 6: Accessibility Conformance

**User Story:** As a user relying on assistive technology, I want the console to meet WCAG AA, so that I can operate every feature with a keyboard and a screen reader.

#### Acceptance Criteria

1. THE Operations_Console SHALL provide text color and background color combinations that meet a contrast ratio of at least 4.5:1 for normal-size text, where normal-size text is text smaller than 18pt, or smaller than 14pt when bold.
2. THE Operations_Console SHALL provide text color and background color combinations that meet a contrast ratio of at least 3:1 for large-size text and for Status_Indicator graphical elements, where large-size text is text of at least 18pt, or at least 14pt when bold.
3. THE Status_Indicator elements SHALL convey state through a text label or icon in addition to color.
4. WHEN an interactive element receives keyboard focus, THE Operations_Console SHALL display a visible focus indicator on that element that has a contrast ratio of at least 3:1 against the adjacent colors of the same element when unfocused.
5. THE Operations_Console SHALL expose each Touch_Target with a minimum hit area of 44px by 44px.
6. WHEN a Data_State changes to error, THE Operations_Console SHALL announce the error through an assertive live region within 1 second of the state change, and the announcement SHALL include a text description of the error.
7. WHEN a Data_State changes to loading, THE Operations_Console SHALL announce the loading state through a polite live region within 1 second of the state change.
8. WHERE a form input has an associated validation message, THE Operations_Console SHALL link the validation message to the input through an accessible description reference that exposes the full message text.
9. WHERE a chart renders telemetry data, THE Live_Telemetry_View SHALL provide an accessible text alternative that includes the latest value, the metric unit, and the timestamp of the latest value.
10. WHERE the user has enabled the reduced-motion system setting, THE Operations_Console SHALL disable all non-essential animation, where non-essential animation is any animation not required to convey current state or task progress.
11. WHEN the user operates the Operations_Console using only a keyboard, THE Operations_Console SHALL allow the user to reach and activate every interactive element without requiring a pointing device.
12. WHILE keyboard focus is on any interactive element, THE Operations_Console SHALL allow the user to move focus away from that element using standard keyboard navigation keys without becoming trapped.

### Requirement 7: Data-State Feedback and UX Clarity

**User Story:** As an operations technician, I want clear loading, empty, error, and live-data cues, so that I can trust what the console is showing me.

#### Acceptance Criteria

1. WHILE a Data_State is loading, THE Operations_Console SHALL display a loading indicator for the affected view within 300 milliseconds of the request starting.
2. IF a Data_State remains loading for more than 30 seconds, THEN THE Operations_Console SHALL stop the loading indicator and display an error message indicating a request timeout with a retry control.
3. WHILE a Data_State is empty, THE Operations_Console SHALL display an empty-state message that names the missing data for the affected view.
4. IF a data request fails, THEN THE Operations_Console SHALL display an error message that identifies the affected view, states the failure reason, and presents a retry control, while preserving any previously loaded data for that view.
5. WHEN a user activates the retry control, THE Operations_Console SHALL re-request the data for the affected view and return to the loading Data_State for that view.
6. WHILE the Live_Telemetry_View renders an interpolated synthetic trace, THE Live_Telemetry_View SHALL display a persistent text label that distinguishes synthetic data from live packet data.
7. WHEN a live WebSocket connection state changes, THE Live_Telemetry_View SHALL update the connection Status_Indicator within 1 second to one of exactly three mutually distinct visual treatments corresponding to the connected, connecting, and disconnected states.
8. THE Operations_Console SHALL present internal endpoint URLs only within the Local Config route and SHALL NOT present internal endpoint URLs in any other route.

### Requirement 8: Theming and Color Scheme

**User Story:** As a user working in varied lighting, I want light and dark themes, so that the console is comfortable to read in any environment.

#### Acceptance Criteria

1. THE Operations_Console SHALL provide a light color theme and a dark color theme.
2. WHEN the application loads without a stored theme preference and the operating system color-scheme setting is light or dark, THE Operations_Console SHALL apply the theme matching that operating system color-scheme setting.
3. IF the application loads without a stored theme preference and the operating system color-scheme setting cannot be determined, THEN THE Operations_Console SHALL apply the light color theme as the default.
4. WHEN the application loads with a stored theme preference, THE Operations_Console SHALL apply the stored theme.
5. WHEN a user selects a theme, THE Operations_Console SHALL apply the selected theme to all routes within 500 milliseconds without requiring a full page reload.
6. WHEN a user selects a theme, THE Operations_Console SHALL persist the selected theme for subsequent sessions in the same browser.
7. IF persisting the selected theme fails, THEN THE Operations_Console SHALL keep the selected theme applied for the current session and display a message indicating that the preference could not be saved.
8. WHILE either theme is active, THE Operations_Console SHALL maintain the contrast ratios defined in Requirement 6.
