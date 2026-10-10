import React from 'react';
import {
  AbsoluteFill,
  Easing,
  interpolate,
  Sequence,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import { COACH_MARK, COLORS, EASE_IN_OUT, MONO } from './theme';

/**
 * Scene wrapper: cross-fades in and out and lifts slightly on entry.
 *
 * IMPORTANT: useCurrentFrame() here executes in the PARENT's sequence context,
 * so it returns the *global* frame. The fade must be computed against the
 * scene-local frame (global - from), otherwise every scene compares its global
 * position against its own short duration and fades straight to zero. That bug
 * renders the film as near-black for its whole length.
 */
export const Scene: React.FC<{
  from: number;
  durationInFrames: number;
  children: React.ReactNode;
  fade?: number;
}> = ({ from, durationInFrames, children, fade = 12 }) => {
  const frame = useCurrentFrame() - from;
  const fadeOutAt = durationInFrames - fade;

  const opacity =
    frame < fade
      ? interpolate(frame, [0, fade], [0, 1], {
          easing: Easing.bezier(...EASE_IN_OUT),
          extrapolateLeft: 'clamp',
          extrapolateRight: 'clamp',
        })
      : frame > fadeOutAt
        ? interpolate(frame, [fadeOutAt, durationInFrames], [1, 0], {
            easing: Easing.bezier(...EASE_IN_OUT),
            extrapolateLeft: 'clamp',
            extrapolateRight: 'clamp',
          })
        : 1;

  const y =
    frame < fade
      ? interpolate(frame, [0, fade], [16, 0], {
          easing: Easing.bezier(...EASE_IN_OUT),
          extrapolateLeft: 'clamp',
          extrapolateRight: 'clamp',
        })
      : 0;

  return (
    <Sequence from={from} durationInFrames={durationInFrames}>
      <AbsoluteFill style={{ opacity, transform: `translateY(${y}px)` }}>
        {children}
      </AbsoluteFill>
    </Sequence>
  );
};

/** Terminal window chrome, shared by every scene. */
export const TerminalFrame: React.FC<{
  children: React.ReactNode;
  title?: string;
  width?: number;
  pad?: number;
  accent?: string;
}> = ({ children, title, width = 1500, pad = 40, accent = COLORS.border }) => (
  <div
    style={{
      width,
      background: COLORS.panel,
      border: `1px solid ${accent}`,
      borderRadius: 14,
      overflow: 'hidden',
      boxShadow: '0 0 0 1px rgba(0,0,0,0.6), 0 40px 90px -30px rgba(0,0,0,0.9)',
      fontFamily: MONO,
      color: COLORS.text,
    }}
  >
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        padding: '14px 20px',
        background: COLORS.panelHi,
        borderBottom: `1px solid ${COLORS.border}`,
      }}
    >
      <div style={{ width: 13, height: 13, borderRadius: 7, background: '#ff5f57' }} />
      <div style={{ width: 13, height: 13, borderRadius: 7, background: '#febc2e' }} />
      <div style={{ width: 13, height: 13, borderRadius: 7, background: '#28c840' }} />
      {title && (
        <div style={{ marginLeft: 14, color: COLORS.dim, fontSize: 21, letterSpacing: 0.4 }}>
          {title}
        </div>
      )}
    </div>
    <div style={{ padding: pad }}>{children}</div>
  </div>
);

/** Reveals text one character at a time. */
export const Typewriter: React.FC<{
  text: string;
  charsPerFrame?: number;
  startDelay?: number;
  style?: React.CSSProperties;
}> = ({ text, charsPerFrame = 1.6, startDelay = 0, style }) => {
  const frame = useCurrentFrame();
  const shown = Math.floor(Math.max(0, frame - startDelay) * charsPerFrame);
  return <span style={style}>{text.slice(0, shown)}</span>;
};

/** Blinking block cursor. */
export const Cursor: React.FC<{ color?: string; size?: number }> = ({
  color = COLORS.green,
  size = 26,
}) => {
  const frame = useCurrentFrame();
  const on = Math.floor(frame / 8) % 2 === 0;
  return (
    <span
      style={{
        display: 'inline-block',
        width: size * 0.55,
        height: size,
        marginLeft: 8,
        background: on ? color : 'transparent',
        verticalAlign: 'text-bottom',
      }}
    />
  );
};

/** ASCII coach rendered as a chat avatar. */
export const CoachAvatar: React.FC<{ size?: number }> = ({ size = 20 }) => (
  <pre
    style={{
      margin: 0,
      fontSize: size * 0.52,
      lineHeight: 1.02,
      color: COLORS.cyan,
      background: COLORS.bgDeep,
      border: `1px solid ${COLORS.cyanDim}`,
      borderRadius: 10,
      padding: '6px 10px',
    }}
  >
    {COACH_MARK.join('\n')}
  </pre>
);

/**
 * One line of claim above the panel. Every scene gets one so the film never
 * shows an unexplained UI: the headline says what the panel proves.
 */
export const Headline: React.FC<{
  children: React.ReactNode;
  highlight?: string;
  delay?: number;
}> = ({ children, highlight, delay = 2 }) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [delay, delay + 12], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const y = interpolate(frame, [delay, delay + 16], [10, 0], {
    easing: Easing.out(Easing.cubic),
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  return (
    <div
      style={{
        fontFamily: MONO,
        fontSize: 38,
        color: COLORS.text,
        letterSpacing: 0.5,
        textAlign: 'center',
        marginBottom: 26,
        opacity,
        transform: `translateY(${y}px)`,
      }}
    >
      {children}
      {highlight && (
        <>
          {' '}
          <span style={{ color: COLORS.cyan }}>{highlight}</span>
        </>
      )}
    </div>
  );
};

/** Supporting line under a headline. */
export const Caption: React.FC<{ children: React.ReactNode; color?: string }> = ({
  children,
  color = COLORS.dim,
}) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [10, 26], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  return (
    <div
      style={{
        marginTop: 24,
        fontFamily: MONO,
        fontSize: 23,
        color,
        textAlign: 'center',
        opacity,
      }}
    >
      {children}
    </div>
  );
};

/**
 * Segmented skill meter. Segments read more clearly than a continuous bar at
 * small sizes and make the 1-10 scale literal.
 */
export const SegmentedMeter: React.FC<{
  value: number;
  color: string;
  segments?: number;
  delay: number;
}> = ({ value, color, segments = 10, delay }) => {
  const frame = useCurrentFrame();
  const filled = interpolate(frame, [delay, delay + 24], [0, value], {
    easing: Easing.out(Easing.cubic),
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  return (
    <div style={{ display: 'flex', gap: 4 }}>
      {Array.from({ length: segments }).map((_, i) => (
        <div
          key={i}
          style={{
            width: 24,
            height: 26,
            borderRadius: 4,
            background: i < filled ? color : COLORS.border,
          }}
        />
      ))}
    </div>
  );
};

/** Card that springs in. */
export const PopIn: React.FC<{
  delay: number;
  children: React.ReactNode;
  style?: React.CSSProperties;
}> = ({ delay, children, style }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = Math.max(0, frame - delay) / fps;
  const e = Math.min(1, t / 0.42);
  const ease = 1 - Math.pow(1 - e, 3);
  return (
    <div
      style={{
        opacity: ease,
        transform: `translateY(${(1 - ease) * 22}px)`,
        ...style,
      }}
    >
      {children}
    </div>
  );
};

/** Row-by-row reveal used for lists that should read as "arriving". */
export const Stagger: React.FC<{
  index: number;
  delay: number;
  step?: number;
  children: React.ReactNode;
  style?: React.CSSProperties;
}> = ({ index, delay, step = 7, children, style }) => (
  <PopIn delay={delay + index * step} style={style}>
    {children}
  </PopIn>
);
