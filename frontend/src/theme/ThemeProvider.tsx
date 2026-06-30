import {
  createContext,
  useCallback,
  useContext,
  useLayoutEffect,
  useMemo,
  useState,
  type ReactNode
} from "react";

// =============================================================================
// Theme System — Elevator PDM Operations Console
// Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7
// =============================================================================

export type ThemeName = "light" | "dark";

export type ThemeSource = "stored" | "system" | "default";

export interface ThemeContextValue {
  /** Currently applied theme. */
  theme: ThemeName;
  /** How the current theme was resolved on the latest setter call. */
  source: ThemeSource;
  /** Applies and persists the requested theme. Requirements 8.5, 8.6, 8.7. */
  setTheme: (next: ThemeName) => void;
  /** Convenience flip between light and dark. */
  toggleTheme: () => void;
  /** True when the last persistence attempt to localStorage failed (Req 8.7). */
  persistenceFailed: boolean;
}

/** localStorage key for the persisted theme preference. */
export const THEME_STORAGE_KEY = "elevator-pdm.theme";

function readStoredTheme(): ThemeName | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    const raw = window.localStorage.getItem(THEME_STORAGE_KEY);
    if (raw === "light" || raw === "dark") {
      return raw;
    }
  } catch {
    // Storage may be unavailable (private mode, security policy, disabled cookies).
    // Treat as "no stored preference" and fall through to OS detection.
  }
  return null;
}

function detectSystemTheme(): ThemeName | null {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return null;
  }
  // Requirement 8.2: match the OS color-scheme when it can be determined.
  if (window.matchMedia("(prefers-color-scheme: dark)").matches) {
    return "dark";
  }
  if (window.matchMedia("(prefers-color-scheme: light)").matches) {
    return "light";
  }
  return null;
}

/**
 * Resolve the initial theme using the documented precedence:
 *   1. stored preference (Requirement 8.4)
 *   2. OS prefers-color-scheme (Requirement 8.2)
 *   3. light default (Requirement 8.3)
 */
export function resolveInitialTheme(): { theme: ThemeName; source: ThemeSource } {
  const stored = readStoredTheme();
  if (stored !== null) {
    return { theme: stored, source: "stored" };
  }

  const system = detectSystemTheme();
  if (system !== null) {
    return { theme: system, source: "system" };
  }

  return { theme: "light", source: "default" };
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

interface ThemeProviderProps {
  children: ReactNode;
}

/**
 * ThemeProvider applies `data-theme` to `<html>` so the CSS tokens under
 * `[data-theme="dark"]` in `src/styles/tokens.css` swap without a reload
 * (Requirement 8.5). Persistence uses localStorage under `elevator-pdm.theme`;
 * on persistence failure the theme remains applied for the session and the
 * `persistenceFailed` flag is raised (Requirement 8.7).
 */
export function ThemeProvider({ children }: ThemeProviderProps): JSX.Element {
  const [state, setState] = useState<{ theme: ThemeName; source: ThemeSource }>(() =>
    resolveInitialTheme()
  );
  const [persistenceFailed, setPersistenceFailed] = useState(false);

  // Apply the data-theme attribute synchronously after every theme change so the
  // CSS variables flip with no flash and well within the 500ms switching budget.
  useLayoutEffect(() => {
    if (typeof document === "undefined") {
      return;
    }
    document.documentElement.setAttribute("data-theme", state.theme);
  }, [state.theme]);

  const persist = useCallback((next: ThemeName) => {
    if (typeof window === "undefined") {
      // Treat the absence of a window as a successful no-op; persistence
      // only applies in a browser session (Requirement 8.6).
      setPersistenceFailed(false);
      return;
    }
    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, next);
      setPersistenceFailed(false);
    } catch {
      // Requirement 8.7: keep the theme applied and surface a non-blocking flag.
      setPersistenceFailed(true);
    }
  }, []);

  const setTheme = useCallback(
    (next: ThemeName) => {
      setState({ theme: next, source: "stored" });
      persist(next);
    },
    [persist]
  );

  const toggleTheme = useCallback(() => {
    setState((prev) => {
      const next: ThemeName = prev.theme === "light" ? "dark" : "light";
      persist(next);
      return { theme: next, source: "stored" };
    });
  }, [persist]);

  const value = useMemo<ThemeContextValue>(
    () => ({
      theme: state.theme,
      source: state.source,
      setTheme,
      toggleTheme,
      persistenceFailed
    }),
    [state.theme, state.source, setTheme, toggleTheme, persistenceFailed]
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

/**
 * Access the theme context. Must be called inside a `<ThemeProvider>`.
 */
export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (ctx === null) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return ctx;
}
