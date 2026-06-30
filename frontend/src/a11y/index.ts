// Public surface of the a11y module.
// Consumers (App, DataState, route pages, tests) should import from
// "./a11y" rather than reaching into individual files.

export { LiveRegionProvider, useAnnouncer } from "./LiveRegionProvider";
export type { Announcer } from "./LiveRegionProvider";

export {
  parseColor,
  composite,
  relativeLuminance,
  contrastRatio,
  resolveToken,
  resolveBackgroundLayers,
  contrastForPairing,
  THEME_TOKEN_VALUES,
  TOKEN_PAIRINGS,
} from "./contrast";
export type {
  RGBAColor,
  ThemeName,
  PairingCategory,
  ContrastThreshold,
  TokenPairing,
  TokenValues,
} from "./contrast";
