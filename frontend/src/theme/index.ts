// Public surface of the theme module.
// Consumers (App, NavigationShell, Storybook, tests) should import from
// "./theme" rather than reaching into individual files.

export {
  ThemeProvider,
  useTheme,
  resolveInitialTheme,
  THEME_STORAGE_KEY
} from "./ThemeProvider";
export type { ThemeName, ThemeSource, ThemeContextValue } from "./ThemeProvider";
export { ThemeToggle } from "./ThemeToggle";
