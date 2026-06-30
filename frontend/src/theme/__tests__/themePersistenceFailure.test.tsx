// Feature: ui-ux-responsive-redesign
// Unit tests for theme persistence failure handling (Requirement 8.7).
//
// Validates: Requirements 8.7
//
// Requirement 8.7 (verbatim):
//   IF persisting the selected theme fails, THEN the Operations_Console SHALL
//   keep the selected theme applied for the current session and display a
//   message indicating that the preference could not be saved.
//
// What these tests verify against the existing ThemeProvider:
//   1. When `localStorage.setItem` throws while `setTheme` is invoked, the
//      newly selected theme is still applied to `document.documentElement`
//      via the `data-theme` attribute (so the theme is visually applied for
//      the current session).
//   2. The `persistenceFailed` flag returned by `useTheme()` becomes `true`,
//      which is the documented mechanism a consumer (e.g. the navigation
//      shell) uses to render a non-blocking "could not save preference"
//      message. A minimal in-test consumer demonstrates this surfacing.
//   3. The theme state continues to reflect the selected theme across
//      subsequent renders (the failure does not silently revert the theme).
//   4. When a later persistence attempt succeeds (storage becomes writable
//      again), `persistenceFailed` clears to `false` so the message no
//      longer surfaces.
//   5. `toggleTheme` exhibits the same behavior as `setTheme` when storage
//      throws, because both go through the same persistence path.

import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  THEME_STORAGE_KEY,
  ThemeProvider,
  useTheme,
  type ThemeName
} from "../ThemeProvider";

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

/**
 * Minimal consumer component that surfaces the entire `useTheme()` contract
 * as DOM nodes so each assertion can target a stable test id. The
 * "persistence-message" node is rendered conditionally on `persistenceFailed`
 * to demonstrate that the flag is the mechanism by which the documented
 * non-blocking message is displayed (Requirement 8.7).
 */
function ThemeProbe(): JSX.Element {
  const { theme, source, persistenceFailed, setTheme, toggleTheme } = useTheme();
  return (
    <div>
      <span data-testid="probe-theme">{theme}</span>
      <span data-testid="probe-source">{source}</span>
      <span data-testid="probe-persistence-failed">{String(persistenceFailed)}</span>
      {persistenceFailed ? (
        <p role="status" data-testid="probe-persistence-message">
          Theme preference could not be saved.
        </p>
      ) : null}
      <button
        type="button"
        data-testid="probe-set-light"
        onClick={() => setTheme("light")}
      >
        light
      </button>
      <button
        type="button"
        data-testid="probe-set-dark"
        onClick={() => setTheme("dark")}
      >
        dark
      </button>
      <button type="button" data-testid="probe-toggle" onClick={toggleTheme}>
        toggle
      </button>
    </div>
  );
}

/**
 * Install a deterministic `window.matchMedia` stub so the initial theme
 * resolves predictably to "light". jsdom does not implement matchMedia.
 */
function stubMatchMediaLight(): void {
  const matcher = (query: string): MediaQueryList => {
    const normalized = query.replace(/\s+/g, " ").trim();
    return {
      matches: normalized === "(prefers-color-scheme: light)",
      media: normalized,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false
    } as unknown as MediaQueryList;
  };
  (window as unknown as { matchMedia: typeof window.matchMedia }).matchMedia =
    matcher as typeof window.matchMedia;
}

/**
 * Replace `window.localStorage.setItem` with an implementation that throws
 * for the theme key (modelling a quota/security failure for that specific
 * write while leaving the rest of localStorage untouched). Returns the spy
 * so individual tests can inspect call counts.
 */
function makeSetItemThrow(): ReturnType<typeof vi.spyOn> {
  return vi
    .spyOn(Storage.prototype, "setItem")
    .mockImplementation((key: string) => {
      if (key === THEME_STORAGE_KEY) {
        throw new DOMException("QuotaExceededError", "QuotaExceededError");
      }
      // Pass through any other unrelated writes to the real implementation
      // by performing a direct property write on the underlying store.
      // Tests in this file only write the theme key, so this branch is
      // defensive and never exercised in practice.
    });
}

// ---------------------------------------------------------------------------
// Suite
// ---------------------------------------------------------------------------

describe("Theme persistence failure (Requirement 8.7)", () => {
  beforeEach(() => {
    window.localStorage.clear();
    document.documentElement.removeAttribute("data-theme");
    stubMatchMediaLight();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    window.localStorage.clear();
    document.documentElement.removeAttribute("data-theme");
  });

  it("keeps the selected theme applied when localStorage.setItem throws on setTheme", () => {
    const setItemSpy = makeSetItemThrow();

    render(
      <ThemeProvider>
        <ThemeProbe />
      </ThemeProvider>
    );

    // Sanity: initial resolution is the light default and no failure yet.
    expect(screen.getByTestId("probe-theme").textContent).toBe("light");
    expect(screen.getByTestId("probe-persistence-failed").textContent).toBe("false");
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");

    // Act: switch to the dark theme; the persistence step must throw.
    act(() => {
      screen.getByTestId("probe-set-dark").click();
    });

    // 1. The theme is applied to <html> for the current session.
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    // 2. The component-level theme state still reports the selected theme.
    expect(screen.getByTestId("probe-theme").textContent).toBe("dark");
    // 3. The persistence step was actually attempted (and threw).
    expect(setItemSpy).toHaveBeenCalledWith(THEME_STORAGE_KEY, "dark" satisfies ThemeName);
    // 4. The non-blocking message indicator surfaces via persistenceFailed.
    expect(screen.getByTestId("probe-persistence-failed").textContent).toBe("true");
    expect(screen.getByTestId("probe-persistence-message")).toBeInTheDocument();
  });

  it("does not write the failed preference into localStorage", () => {
    makeSetItemThrow();

    render(
      <ThemeProvider>
        <ThemeProbe />
      </ThemeProvider>
    );

    act(() => {
      screen.getByTestId("probe-set-dark").click();
    });

    // The throwing setItem prevents persistence; the storage entry must not
    // exist, so a future reload would fall back to OS/default per the
    // resolution precedence (Requirements 8.2-8.4).
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBeNull();
    // The theme nevertheless remains applied for this session.
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
  });

  it("keeps the selected theme across subsequent renders after a persistence failure", () => {
    makeSetItemThrow();

    const { rerender } = render(
      <ThemeProvider>
        <ThemeProbe />
      </ThemeProvider>
    );

    act(() => {
      screen.getByTestId("probe-set-dark").click();
    });

    // Force a re-render of the consumer subtree; the provider keeps the
    // session theme because the in-memory state is unaffected by the
    // persistence failure.
    rerender(
      <ThemeProvider>
        <ThemeProbe />
      </ThemeProvider>
    );

    // Note: the provider re-mounts on rerender of a fresh element identity
    // only if React detects a new type — here the wrapper element is the
    // same, so state is preserved and the theme remains "dark".
    expect(screen.getByTestId("probe-theme").textContent).toBe("dark");
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    expect(screen.getByTestId("probe-persistence-failed").textContent).toBe("true");
  });

  it("clears persistenceFailed once a later persistence attempt succeeds", () => {
    const setItemSpy = makeSetItemThrow();

    render(
      <ThemeProvider>
        <ThemeProbe />
      </ThemeProvider>
    );

    // First call fails — flag should rise and message should appear.
    act(() => {
      screen.getByTestId("probe-set-dark").click();
    });
    expect(screen.getByTestId("probe-persistence-failed").textContent).toBe("true");
    expect(screen.getByTestId("probe-persistence-message")).toBeInTheDocument();

    // Storage becomes writable again — restore the original setItem.
    setItemSpy.mockRestore();

    act(() => {
      screen.getByTestId("probe-set-light").click();
    });

    // The flag clears, the message goes away, and the new theme is applied
    // both in state and on <html>.
    expect(screen.getByTestId("probe-persistence-failed").textContent).toBe("false");
    expect(screen.queryByTestId("probe-persistence-message")).not.toBeInTheDocument();
    expect(screen.getByTestId("probe-theme").textContent).toBe("light");
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("light");
  });

  it("surfaces persistenceFailed when toggleTheme triggers a persistence failure", () => {
    makeSetItemThrow();

    render(
      <ThemeProvider>
        <ThemeProbe />
      </ThemeProvider>
    );

    // Starting state is light (set by stubMatchMediaLight + no stored pref).
    expect(screen.getByTestId("probe-theme").textContent).toBe("light");

    act(() => {
      screen.getByTestId("probe-toggle").click();
    });

    // toggleTheme flipped to dark; persistence threw; flag must be set and
    // the theme remains applied for the session.
    expect(screen.getByTestId("probe-theme").textContent).toBe("dark");
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    expect(screen.getByTestId("probe-persistence-failed").textContent).toBe("true");
    expect(screen.getByTestId("probe-persistence-message")).toBeInTheDocument();
  });
});
