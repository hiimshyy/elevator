import { useTheme } from "./ThemeProvider";

// =============================================================================
// ThemeToggle — light/dark switch control
// Requirements: 8.1, 8.5, 8.6
// Designed to be mounted later by the Navigation_Shell (task 12.1).
// =============================================================================

interface ThemeToggleProps {
  /** Optional extra class for shell-level layout. */
  className?: string;
}

export function ThemeToggle({ className }: ThemeToggleProps = {}): JSX.Element {
  const { theme, toggleTheme } = useTheme();
  const isDark = theme === "dark";
  const nextThemeLabel = isDark ? "light" : "dark";
  const classes = ["theme-toggle", className].filter(Boolean).join(" ");

  return (
    <button
      type="button"
      className={classes}
      onClick={toggleTheme}
      aria-label={`Switch to ${nextThemeLabel} theme`}
      aria-pressed={isDark}
      title={`Switch to ${nextThemeLabel} theme`}
      data-testid="theme-toggle"
    >
      <span className="theme-toggle__icon" aria-hidden="true">
        {isDark ? "☀️" : "🌙"}
      </span>
      <span className="theme-toggle__label">{isDark ? "Light" : "Dark"}</span>
    </button>
  );
}
