/**
 * Visual language for the promo.
 *
 * The palette is the app's own Textual dark theme so the film and the product
 * read as the same thing. Monospace throughout, because the product is a
 * terminal application.
 */

export const COLORS = {
  bg: '#0a0e14',
  bgDeep: '#05070b',
  panel: '#11161d',
  panelHi: '#161c24',
  border: '#242c36',
  borderHi: '#39424e',

  green: '#3fb950',
  greenDim: '#2ea043',
  cyan: '#39c5cf',
  cyanDim: '#1f6f78',
  amber: '#d29922',
  red: '#f85149',

  text: '#e6edf3',
  dim: '#8b949e',
  dimmer: '#57606a',
} as const;

export const MONO =
  '"JetBrains Mono", "Cascadia Mono", "SF Mono", Consolas, "DejaVu Sans Mono", monospace';

export const FPS = 30;
export const WIDTH = 1920;
export const HEIGHT = 1080;
export const DURATION = 900; // 30s

/**
 * Scene boundaries, in frames.
 *
 * The hook is short -- it only has to land a question. Every feature scene needs
 * room for its content to arrive, be read, and react before it leaves.
 */
export const SCENES = {
  hook: { from: 0, durationInFrames: 92 },
  assess: { from: 92, durationInFrames: 158 },
  plan: { from: 250, durationInFrames: 158 },
  coach: { from: 408, durationInFrames: 152 },
  profile: { from: 560, durationInFrames: 150 },
  review: { from: 710, durationInFrames: 130 },
  outro: { from: 840, durationInFrames: 60 },
} as const;

export const EASE_OUT = [0.16, 1, 0.3, 1] as const;
export const EASE_IN_OUT = [0.65, 0, 0.35, 1] as const;

/** Small ASCII coach, used as an avatar and on the title card. ASCII only:
 *  Windows terminals render many Unicode drawing characters as tofu. */
export const COACH_MARK = [
  '  .-------.',
  ' /  o   o  \\',
  '|     ^     |',
  " \\  '---'  /",
  "  '-------'",
] as const;
