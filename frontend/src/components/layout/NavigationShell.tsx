import { useReducer, useEffect, useRef, useCallback, type ReactNode } from "react";
import { NavLink, Outlet } from "react-router-dom";

import { useBreakpoint } from "../../hooks/useBreakpoint";
import { ThemeToggle } from "../../theme/ThemeToggle";

import "./NavigationShell.css";

// =============================================================================
// NavigationShell — Elevator PDM Operations Console
// Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 7.8
//
// This component replaces the existing AppShell. Wiring into App.tsx /
// main.tsx is deferred to task 20.1; this module only ships the shell and
// the pure nav-toggle reducer used by both the component and the property
// test in task 12.2.
//
// Behavior summary (from design.md):
//   - Desktop / Large_Desktop: persistent sidebar (Req 5.1).
//   - Mobile / Tablet: nav collapsed behind a single menu control (Req 5.2).
//     Activating the menu toggles expand/collapse (Req 5.3, 5.4). Selecting
//     a link navigates and collapses the nav (Req 5.5).
//   - Transitioning up to Desktop / Large while expanded shows the
//     persistent sidebar (Req 5.6) — handled implicitly because the sidebar
//     is always visible in persistent mode, regardless of `isExpanded`.
//   - Active link uses `aria-current="page"` (set automatically by NavLink)
//     plus a non-color distinction (left rail indicator + bold weight) on
//     top of any color change (Req 5.7).
//   - Includes a skip-to-content link and the `ThemeToggle`.
//   - The current AppShell's brand block surfaces the endpoint URL and a
//     "default/custom endpoint" status pill; both are removed here so that
//     endpoint URLs only appear on the Local Config route (Req 7.8).
//
// The nav-toggle reducer and its action types are exported so the property
// test in task 12.2 can target them directly without rendering the
// component.
// =============================================================================

/**
 * Static navigation table. Order here determines the rendered order in the
 * sidebar. Same four routes as the legacy AppShell so wiring later (task
 * 20.1) only swaps the shell component, not the routes.
 */
export const NAV_ITEMS = [
  { to: "/fleet", label: "Fleet Overview" },
  { to: "/live", label: "Live Monitor" },
  { to: "/alerts", label: "Alerts & Maintenance" },
  { to: "/config", label: "Local Config" },
] as const;

/**
 * State of the nav toggle. Only `isExpanded` matters in collapsible mode
 * (mobile/tablet); in persistent mode (desktop/large) the sidebar is shown
 * unconditionally and this flag is ignored.
 */
export interface NavState {
  /** True when the collapsible nav drawer is currently open. */
  isExpanded: boolean;
}

/**
 * Discriminated union of actions accepted by {@link navReducer}.
 *   - `toggle`     — flips `isExpanded` (an involution; Req 5.3, 5.4).
 *   - `selectLink` — collapses the nav, regardless of prior state (Req 5.5).
 */
export type NavAction = { type: "toggle" } | { type: "selectLink" };

/** Initial state used by the component reducer and by the property test. */
export const initialNavState: NavState = { isExpanded: false };

/**
 * Pure reducer for the navigation toggle. Exported so it can be unit-tested
 * separately (design § "Define and export a pure nav-toggle reducer ..."):
 *
 *   - For all states s, `navReducer(navReducer(s, toggle), toggle) === s`
 *     (involution — Property 4 part 1).
 *   - For all states s, `navReducer(s, selectLink).isExpanded === false`
 *     (link selection collapses — Property 4 part 2).
 */
export function navReducer(state: NavState, action: NavAction): NavState {
  switch (action.type) {
    case "toggle":
      return { isExpanded: !state.isExpanded };
    case "selectLink":
      return { isExpanded: false };
    default: {
      // Exhaustiveness guard. If a new action type is added the type system
      // will surface the missing case here.
      const _exhaustive: never = action;
      return _exhaustive;
    }
  }
}

interface NavigationShellProps {
  /**
   * Optional content to render inside `<main>` instead of the router
   * `<Outlet />`. Useful for tests and storybook; production code paths
   * (App.tsx wiring in task 20.1) leave this undefined so the outlet
   * renders the matched route.
   */
  children?: ReactNode;
}

/**
 * Application chrome: skip link, top bar (brand + theme toggle + menu
 * button on small screens), sidebar with the primary nav, and the main
 * content area. Responsive behavior is driven by `useBreakpoint()` for the
 * collapsible/persistent decision; CSS handles the rest via the
 * `data-nav-mode` and `data-expanded` attributes on the root element.
 */
export function NavigationShell({ children }: NavigationShellProps = {}): JSX.Element {
  const { isNavCollapsible } = useBreakpoint();
  const [navState, dispatch] = useReducer(navReducer, initialNavState);
  const menuButtonRef = useRef<HTMLButtonElement>(null);

  const navMode = isNavCollapsible ? "collapsible" : "persistent";
  // The sidebar is shown either when the breakpoint is persistent (Req 5.1,
  // 5.6) or when the user has expanded the collapsible drawer (Req 5.3).
  const isSidebarVisible = !isNavCollapsible || navState.isExpanded;
  const menuButtonLabel = navState.isExpanded ? "Close navigation" : "Open navigation";

  const handleLinkSelect = (): void => {
    // Collapse only in collapsible mode (Req 5.5). In persistent mode the
    // sidebar is always visible, so dispatching `selectLink` would be a
    // no-op for the UI but would still flip `isExpanded` from a possibly
    // stale `true` value carried over from a recent collapsible session;
    // skipping the dispatch keeps the reducer's state untouched in the
    // persistent case.
    if (isNavCollapsible) {
      dispatch({ type: "selectLink" });
    }
  };

  // Close the drawer on ESC key press (Req 6.12 — no focus traps).
  // When the drawer closes, focus returns to the menu button.
  const handleKeyDown = useCallback(
    (event: KeyboardEvent): void => {
      if (event.key === "Escape" && navState.isExpanded && isNavCollapsible) {
        dispatch({ type: "selectLink" });
        menuButtonRef.current?.focus();
      }
    },
    [navState.isExpanded, isNavCollapsible],
  );

  useEffect(() => {
    if (navState.isExpanded && isNavCollapsible) {
      document.addEventListener("keydown", handleKeyDown);
      return () => document.removeEventListener("keydown", handleKeyDown);
    }
  }, [navState.isExpanded, isNavCollapsible, handleKeyDown]);

  return (
    <div
      className="navshell"
      data-nav-mode={navMode}
      data-expanded={navState.isExpanded ? "true" : "false"}
    >
      {/*
        Skip-to-content link — visually hidden until focused. Lets keyboard
        and screen-reader users bypass the nav and land directly in the
        main region (design § "Include a skip-to-content link").
      */}
      <a className="navshell__skip-link" href="#main-content">
        Skip to main content
      </a>

      <header className="navshell__topbar">
        {/*
          Menu control is only rendered in collapsible mode (Req 5.2). It
          controls the sidebar element via `aria-controls`, and its
          expanded state is exposed through `aria-expanded` so AT can
          report the drawer state.
        */}
        {isNavCollapsible ? (
          <button
            type="button"
            className="navshell__menu-button"
            ref={menuButtonRef}
            onClick={() => dispatch({ type: "toggle" })}
            aria-expanded={navState.isExpanded}
            aria-controls="primary-navigation"
            aria-label={menuButtonLabel}
            data-testid="nav-menu-button"
          >
            <span aria-hidden="true" className="navshell__menu-icon">
              {navState.isExpanded ? "✕" : "☰"}
            </span>
          </button>
        ) : null}

        <div className="navshell__brand">
          <span className="navshell__brand-eyebrow">Elevator PDM</span>
          <strong className="navshell__brand-title">Operations Console</strong>
        </div>

        <ThemeToggle className="navshell__theme-toggle" />
      </header>

      <aside
        id="primary-navigation"
        className="navshell__sidebar"
        aria-label="Primary"
        data-visible={isSidebarVisible ? "true" : "false"}
      >
        <nav className="navshell__nav" aria-label="Primary navigation">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end
              className={({ isActive }) =>
                ["navshell__link", isActive ? "navshell__link--active" : null]
                  .filter((part): part is string => Boolean(part))
                  .join(" ")
              }
              onClick={handleLinkSelect}
            >
              {/*
                Rail indicator is a non-color signal of the active link
                (Req 5.7). It is hidden by default and made visible via
                the `.navshell__link[aria-current="page"]` selector in
                NavigationShell.css; `aria-hidden` keeps the empty span
                out of the accessibility tree.
              */}
              <span className="navshell__link-rail" aria-hidden="true" />
              <span className="navshell__link-label">{item.label}</span>
            </NavLink>
          ))}
        </nav>
      </aside>

      <main id="main-content" className="navshell__main" tabIndex={-1}>
        {children ?? <Outlet />}
      </main>
    </div>
  );
}
