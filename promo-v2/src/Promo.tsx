import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { COLORS, SCENES } from './theme';
import {
  Caption,
  CoachAvatar,
  Cursor,
  Headline,
  PopIn,
  Scene,
  SegmentedMeter,
  Stagger,
  TerminalFrame,
  Typewriter,
} from './components';

/**
 * Every string below is taken from the application's own code, not invented:
 *   - persona presets and blurbs   -> src/persona.py (PERSONA_PRESETS)
 *   - the corrections shape        -> src/daily_coach.py
 *   - the five skill dimensions    -> src/dynamic_profile.py (SkillScores)
 *   - the "set to" directives      -> src/coach_policy.py (SessionDirectives.render)
 *   - the SM-2 rating labels       -> src/srs.py (RATING_LABELS)
 */

/* ------------------------------------------------------------------ hook */

const Hook: React.FC = () => {
  const line2 = 34;
  const line3 = 62;

  return (
    <AbsoluteFill
      style={{ justifyContent: 'center', alignItems: 'center', fontFamily: 'monospace' }}
    >
      <TerminalFrame width={1260} title="bash — english-coach" pad={52}>
        <div style={{ fontSize: 36, lineHeight: 1.7 }}>
          <div style={{ color: COLORS.dim }}>
            <span style={{ color: COLORS.green }}>$</span> english-coach
            <span style={{ color: COLORS.dimmer }}> — studying alone</span>
          </div>
          <div style={{ height: 26 }} />
          <div style={{ color: COLORS.text, fontFamily: 'monospace' }}>
            {line2 > 0 ? <Typewriter text="Which book? Which level?" charsPerFrame={2} startDelay={10} /> : null}
            <span style={{ color: COLORS.dim }}>
              {line2 ? '  Is this sentence even right?' : ''}
            </span>
          </div>
          <div style={{ height: 14 }} />
          {line3 ? (
            <div style={{ color: COLORS.dimmer }}>
              <Typewriter text="guess. repeat. forget." charsPerFrame={1.6} startDelay={line3} />
            </div>
          ) : null}
          {!line3 && <Cursor size={34} />}
        </div>
      </TerminalFrame>
    </AbsoluteFill>
  );
};

/* -------------------------------------------------------------- assess */

const PERSONAS = [
  { label: 'Friendly partner', sub: 'warm, encouraging' },
  { label: 'Strict examiner', sub: 'corrects every error' },
  { label: 'Business coach', sub: 'concise, professional' },
  { label: 'Socratic tutor', sub: 'guides you to answers' },
];

const ASSESS_ASK = 'Before we start — how would you like to be taught?';
const ASSESS_LEARNER = 'Be patient with me, and explain why.';

const Assess: React.FC = () => (
  <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
    <Headline highlight="who you are">
      First, it finds out
    </Headline>
    <TerminalFrame width={1440} title="English Assessment" pad={38}>
      <div style={{ display: 'flex', gap: 20, alignItems: 'flex-start' }}>
        <CoachAvatar size={18} />
        <div
          style={{
            background: COLORS.bgDeep,
            border: `1px solid ${COLORS.border}`,
            borderRadius: '4px 16px 16px 16px',
            padding: '18px 26px',
            fontSize: 27,
          }}
        >
          <Typewriter text={ASSESS_ASK} charsPerFrame={2} startDelay={4} />
        </div>
      </div>

      <div style={{ display: 'flex', gap: 16, marginTop: 28, marginLeft: 14 }}>
        {PERSONAS.map((p, i) => (
          <Stagger key={p.label} index={i} delay={20} step={5}>
            <div
              style={{
                border: `2px solid ${i === 0 ? COLORS.green : COLORS.border}`,
                background: i === 0 ? 'rgba(63,185,80,0.10)' : COLORS.bgDeep,
                borderRadius: 12,
                padding: '16px 20px',
                width: 296,
                boxShadow: i === 0 ? `0 0 26px -8px ${COLORS.green}` : 'none',
              }}
            >
              <div
                style={{
                  fontSize: 22,
                  color: i === 0 ? COLORS.green : COLORS.text,
                  whiteSpace: 'nowrap',
                }}
              >
                {i === 0 ? '✓ ' : ''}
                {p.label}
              </div>
              <div style={{ fontSize: 19, color: COLORS.dim, marginTop: 7 }}>{p.sub}</div>
            </div>
          </Stagger>
        ))}
      </div>

      <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 26, marginRight: 10 }}>
        <PopIn delay={44}>
          <div
            style={{
              background: COLORS.panelHi,
              border: `1px solid ${COLORS.borderHi}`,
              borderRadius: '16px 4px 16px 16px',
              padding: '15px 24px',
              fontSize: 25,
            }}
          >
            {ASSESS_LEARNER}
          </div>
        </PopIn>
      </div>

      <div style={{ display: 'flex', gap: 14, marginTop: 26, marginLeft: 14, flexWrap: 'wrap' }}>
        {[
          { k: 'Level', v: 'B1' },
          { k: 'Focus', v: 'tense & articles' },
          { k: 'Goal', v: 'business writing' },
          { k: 'Days', v: '14' },
        ].map((c, i) => (
          <Stagger key={c.k} index={i} delay={54} step={6}>
            <div
              style={{
                border: `1px solid ${COLORS.cyanDim}`,
                borderRadius: 999,
                padding: '9px 20px',
                background: 'rgba(57,197,207,0.07)',
              }}
            >
              <span style={{ color: COLORS.dim, fontSize: 21 }}>{c.k} </span>
              <span style={{ color: COLORS.cyan, fontSize: 23 }}>{c.v}</span>
            </div>
          </Stagger>
        ))}
      </div>
    </TerminalFrame>
    <Caption>Level, goals and teacher, set by one conversation</Caption>
  </AbsoluteFill>
);

/* ---------------------------------------------------------------- plan */

const DAYS = [
  { d: 1, topic: 'Telling a story' },
  { d: 2, topic: 'Being precise', revised: true },
  { d: 3, topic: 'Word families' },
  { d: 4, topic: 'Business tone' },
  { d: 5, topic: 'Long answers' },
];

const KNOWLEDGE = [
  { title: 'Hedging language', detail: 'maybe / tend to / arguably' },
  { title: 'Quantifying uncountable nouns', detail: 'a bit of advice, several pieces' },
];

const Plan: React.FC = () => (
  <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
    <Headline highlight="not a textbook">
      A plan built from your profile,
    </Headline>
    <TerminalFrame width={1440} title="Course Plan — 14 days" pad={34}>
      <div style={{ display: 'flex', gap: 26 }}>
        <div style={{ width: 620 }}>
          {DAYS.map((day, i) => (
            <Stagger
              key={day.d}
              index={i}
              delay={8}
              step={8}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 18,
                padding: '12px 18px',
                marginBottom: 9,
                borderRadius: 8,
                background: i === 1 ? 'rgba(57,197,207,0.09)' : COLORS.bgDeep,
                border: `1px solid ${i === 1 ? COLORS.cyanDim : COLORS.border}`,
              }}
            >
              <div
                style={{
                  color: i === 1 ? COLORS.cyan : COLORS.dimmer,
                  fontSize: 23,
                  width: 82,
                  whiteSpace: 'nowrap',
                }}
              >
                Day {day.d}
              </div>
              <div style={{ fontSize: 22, color: COLORS.text }}>{day.topic}</div>
              {day.revised && (
                <div
                  style={{
                    marginLeft: 'auto',
                    color: COLORS.amber,
                    border: `1px solid ${COLORS.amber}`,
                    borderRadius: 5,
                    padding: '2px 9px',
                    fontSize: 17,
                  }}
                >
                  revised
                </div>
              )}
            </Stagger>
          ))}
        </div>

        <PopIn
          delay={40}
          style={{
            flex: 1,
            background: COLORS.bgDeep,
            border: `1px solid ${COLORS.borderHi}`,
            borderRadius: 12,
            padding: 24,
            height: 'fit-content',
          }}
        >
          <div style={{ fontSize: 20, color: COLORS.cyan, letterSpacing: 1 }}>
            DAY 2 · KNOWLEDGE POINTS
          </div>
          <div style={{ marginTop: 18 }}>
            {KNOWLEDGE.map((k, i) => (
              <Stagger key={k.title} index={i} delay={50} step={9} style={{ marginBottom: 13 }}>
                <div style={{ display: 'flex', gap: 13 }}>
                  <span style={{ color: COLORS.green }}>{i + 1}.</span>
                  <div>
                    <div style={{ fontSize: 23, color: COLORS.text }}>{k.title}</div>
                    <div style={{ fontSize: 19, color: COLORS.dim, marginTop: 3 }}>
                      {k.detail}
                    </div>
                  </div>
                </div>
              </Stagger>
            ))}
          </div>
          <div
            style={{
              marginTop: 18,
              paddingTop: 18,
              borderTop: `1px dashed ${COLORS.border}`,
              fontSize: 20,
              color: COLORS.dim,
              lineHeight: 1.8,
            }}
          >
            <div>
              <span style={{ color: COLORS.amber }}>optional stretch</span> — push it to
              academic register
            </div>
            <div>
              <span style={{ color: COLORS.dimmer }}>estimated time</span> — 25 min
            </div>
          </div>
        </PopIn>
      </div>
    </TerminalFrame>
    <Caption>remaining days rewrite themselves after every session</Caption>
  </AbsoluteFill>
);

/* --------------------------------------------------------------- coach */

const Coach: React.FC = () => (
  <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
    <Headline highlight="a reason">
      Every day you talk, and every error gets
    </Headline>
    <TerminalFrame width={1340} title="Day 2 — Being precise · Focus: hedging language" pad={36}>
      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <PopIn delay={6}>
          <div
            style={{
              background: COLORS.panelHi,
              border: `1px solid ${COLORS.borderHi}`,
              borderRadius: '16px 4px 16px 16px',
              padding: '15px 24px',
              fontSize: 26,
            }}
          >
            I have been to Tokyo last year.
          </div>
        </PopIn>
      </div>

      <PopIn delay={22} style={{ marginTop: 22 }}>
        <div style={{ fontSize: 21, color: COLORS.amber, marginBottom: 13 }}>
          Corrections
        </div>
        <div style={{ borderLeft: `3px solid ${COLORS.borderHi}`, paddingLeft: 20 }}>
          <div style={{ fontSize: 22, lineHeight: 1.7 }}>
            <span style={{ color: COLORS.dimmer }}>original: </span>
            <span style={{ color: COLORS.red, textDecoration: 'line-through' }}>
              I have been to Tokyo last year.
            </span>
            <span style={{ color: COLORS.dimmer }}> → </span>
            <span style={{ color: COLORS.green }}>I went to Tokyo last year.</span>
          </div>
          <div style={{ fontSize: 20, lineHeight: 1.6, marginTop: 8, color: COLORS.dim }}>
            <span style={{ color: COLORS.dimmer }}>why: </span>“last year” is finished
            past time — that takes past simple, not present perfect.
          </div>
        </div>
      </PopIn>

      <PopIn delay={66} style={{ marginTop: 24 }}>
        <div style={{ fontSize: 24, color: COLORS.green, lineHeight: 1.6 }}>
          Good catch to make. Now say the same thing using{' '}
          <span style={{ color: COLORS.text }}>“two years ago”</span>
          <Cursor size={22} />
        </div>
      </PopIn>
    </TerminalFrame>
    <Caption>the original, the fix, and the rule behind it</Caption>
  </AbsoluteFill>
);

/* ------------------------------------------------------------- profile */

const SKILLS = [
  { label: 'Grammar', score: 6 },
  { label: 'Vocabulary', score: 6 },
  { label: 'Sentence structure', score: 5 },
  { label: 'Fluency', score: 6 },
  { label: 'Accuracy', score: 4 },
];

const band = (v: number) =>
  v >= 7 ? COLORS.green : v >= 5 ? COLORS.amber : COLORS.red;

// Values below are what build_session_directives() actually computes for these
// scores: average 5.4 -> intermediate, weakest = accuracy, 20 exchanges.
const DIRECTIVES = [
  { key: 'difficulty', value: 'intermediate', note: 'avg 5.4 / 10' },
  { key: 'priority skill', value: 'accuracy', note: 'lowest — 4 / 10' },
  { key: 'session target', value: '20 exchanges', note: '~20 min' },
];

const Profile: React.FC = () => (
  <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
    <Headline highlight="never guesses">
      And it
    </Headline>
    <TerminalFrame width={1360} title="Skill profile — B1 (confidence: medium)" pad={38}>
      <div style={{ display: 'flex', gap: 56 }}>
        <div style={{ flex: 1 }}>
          {SKILLS.map((s, i) => (
            <Stagger
              key={s.label}
              index={i}
              delay={8}
              step={6}
              style={{ display: 'flex', alignItems: 'center', gap: 20, marginBottom: 19 }}
            >
              <div style={{ width: 258, fontSize: 22, color: COLORS.text }}>{s.label}</div>
              <SegmentedMeter value={s.score} color={band(s.score)} delay={10 + i * 6} />
              <div style={{ fontSize: 21, color: COLORS.dim, width: 52 }}>
                {s.score}/10
              </div>
            </Stagger>
          ))}
        </div>

        <div
          style={{
            width: 580,
            background: COLORS.bgDeep,
            border: `1px solid ${COLORS.borderHi}`,
            borderRadius: 12,
            padding: 24,
            height: 'fit-content',
          }}
        >
          <div style={{ fontSize: 20, color: COLORS.cyan, letterSpacing: 1 }}>
            TODAY THE COACH WAS SET TO
          </div>
          <div style={{ marginTop: 18, fontSize: 21, lineHeight: 1.95 }}>
            {DIRECTIVES.map((d, i) => (
              <Stagger key={d.key} index={i} delay={26} step={9}>
                <div>
                  <span style={{ color: COLORS.dimmer }}>{d.key} </span>
                  <span
                    style={{
                      color:
                        d.key === 'priority skill' ? COLORS.red : COLORS.text,
                    }}
                  >
                    {d.value}
                  </span>
                  <span style={{ color: COLORS.dimmer, fontSize: 18 }}> ({d.note})</span>
                </div>
              </Stagger>
            ))}
          </div>
          <div
            style={{
              marginTop: 18,
              paddingTop: 16,
              borderTop: `1px dashed ${COLORS.border}`,
              fontSize: 18,
              color: COLORS.dim,
              lineHeight: 1.6,
            }}
          >
            <PopIn delay={62}>
              computed from your scores in code
              <br />
              the model guessed{' '}
              <span style={{ color: COLORS.red }}>“beginner”</span> — the scores overrode it
            </PopIn>
          </div>
        </div>
      </div>
    </TerminalFrame>
    <Caption>difficulty and focus come from the numbers, not a vibe</Caption>
  </AbsoluteFill>
);

/* -------------------------------------------------------------- review */

const RATINGS = [
  { n: '1', label: 'Again', tone: COLORS.red },
  { n: '2', label: 'Hard', tone: COLORS.amber },
  { n: '3', label: 'Good', tone: COLORS.green },
  { n: '4', label: 'Easy', tone: COLORS.cyan },
];

const ReviewScene: React.FC = () => {
  const frame = useCurrentFrame();
  const revealAt = 16;
  const rateAt = 40;
  // Stay revealed for the rest of the scene. Flipping back to the front after
  // grading would show "unrevealed card + already rated", which reads as a bug.
  const flipped = frame >= revealAt;
  const rated = frame >= rateAt;

  return (
    <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
      <Headline highlight="on schedule">
        Saved phrases come back
      </Headline>
      <TerminalFrame width={1180} title="/review — 3 due" pad={38}>
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            height: 390,
            justifyContent: 'center',
          }}
        >
          <PopIn delay={6} style={{ width: '100%' }}>
            <div
              style={{
                background: flipped ? 'rgba(63,185,80,0.08)' : COLORS.bgDeep,
                border: `2px solid ${flipped ? COLORS.greenDim : COLORS.borderHi}`,
                borderRadius: 14,
                padding: '38px',
                textAlign: 'center',
              }}
            >
              <div style={{ fontSize: 22, color: COLORS.dimmer, marginBottom: 16 }}>
                card 1 of 3
              </div>
              <div style={{ fontSize: 42, color: flipped ? COLORS.green : COLORS.text }}>
                {flipped ? 'to leave the ground' : 'take off'}
              </div>
              <div style={{ fontSize: 20, color: COLORS.dimmer, marginTop: 16 }}>
                {flipped ? 'the plane took off an hour late' : 'press Space to reveal'}
              </div>
            </div>
          </PopIn>

          <PopIn delay={revealAt + 5} style={{ marginTop: 28 }}>
            <div style={{ display: 'flex', gap: 16 }}>
              {RATINGS.map((b) => {
                const active = rated && b.n === '3';
                return (
                  <div
                    key={b.n}
                    style={{
                      border: `2px solid ${active ? b.tone : COLORS.border}`,
                      background: active ? `${b.tone}22` : COLORS.bgDeep,
                      color: active ? b.tone : COLORS.dim,
                      borderRadius: 10,
                      padding: '13px 28px',
                      fontSize: 22,
                      transform: active ? 'scale(1.07)' : 'scale(1)',
                    }}
                  >
                    {b.n} {b.label}
                  </div>
                );
              })}
            </div>
          </PopIn>

          <PopIn delay={rateAt + 8} style={{ marginTop: 22 }}>
            <div
              style={{
                border: `1px solid ${COLORS.cyanDim}`,
                borderRadius: 999,
                padding: '8px 20px',
                background: 'rgba(57,197,207,0.07)',
                color: COLORS.cyan,
                fontSize: 20,
              }}
            >
              next review in 1 day
            </div>
          </PopIn>
        </div>
      </TerminalFrame>
    </AbsoluteFill>
  );
};

/* --------------------------------------------------------------- outro */

const FEATURES = [
  'level assessment',
  'personal course plan',
  'daily corrections',
  'skill profile',
  'spaced repetition',
];

const Outro: React.FC = () => (
  <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center', fontFamily: 'monospace' }}>
    <TerminalFrame width={1240} title="bash" pad={46} accent={COLORS.cyanDim}>
      <div style={{ textAlign: 'center' }}>
        <PopIn delay={2}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 26,
            }}
          >
            <div style={{ fontSize: 20, lineHeight: 1.02, color: COLORS.cyan }}>
              <CoachAvatar size={22} />
            </div>
            <div style={{ fontSize: 62, color: COLORS.text, letterSpacing: 1 }}>
              English Coach
            </div>
          </div>
        </PopIn>
        <PopIn delay={12}>
          <div style={{ fontSize: 25, color: COLORS.dim, marginTop: 20, letterSpacing: 0.5 }}>
            An AI writing coach in your terminal
          </div>
        </PopIn>
        <div
          style={{
            display: 'flex',
            gap: 14,
            justifyContent: 'center',
            marginTop: 30,
            flexWrap: 'wrap',
          }}
        >
          {FEATURES.map((f, i) => (
            <Stagger key={f} index={i} delay={22} step={6}>
              <div
                style={{
                  border: `1px solid ${COLORS.borderHi}`,
                  borderRadius: 999,
                  padding: '8px 20px',
                  color: COLORS.cyan,
                  fontSize: 20,
                }}
              >
                {f}
              </div>
            </Stagger>
          ))}
        </div>
        <PopIn delay={40}>
          <div style={{ fontSize: 22, marginTop: 28, color: COLORS.dim }}>
            <span style={{ color: COLORS.green }}>$</span> python run.py
            <Cursor size={22} />
          </div>
        </PopIn>
      </div>
    </TerminalFrame>
  </AbsoluteFill>
);

/* -------------------------------------------------------------- compose */

export const Promo: React.FC = () => (
  <AbsoluteFill style={{ background: COLORS.bg, overflow: 'hidden' }}>
    <AbsoluteFill
      style={{
        background:
          'radial-gradient(ellipse at 50% 38%, rgba(57,197,207,0.07) 0%, rgba(0,0,0,0) 62%)',
      }}
    />
    <Scene {...SCENES.hook}>
      <Hook />
    </Scene>
    <Scene {...SCENES.assess}>
      <Assess />
    </Scene>
    <Scene {...SCENES.plan}>
      <Plan />
    </Scene>
    <Scene {...SCENES.coach}>
      <Coach />
    </Scene>
    <Scene {...SCENES.profile}>
      <Profile />
    </Scene>
    <Scene {...SCENES.review}>
      <ReviewScene />
    </Scene>
    <Scene {...SCENES.outro}>
      <Outro />
    </Scene>
  </AbsoluteFill>
);
