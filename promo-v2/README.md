# English Coach — promo film (Remotion)

A 30-second product film for English Coach, rendered with
[Remotion](https://remotion.dev). The look matches the product: dark terminal,
monospace throughout, the same accent colours as the app's Textual theme.

> This directory is a self-contained implementation. It shares no source with
> the sibling `promo/` directory.

## Scenes

| Frames | Time | Shows |
|--------|------|-------|
| 0–92 | 0:00–0:03 | Hook — learning alone means guessing what to study |
| 92–250 | 0:03–0:08.3 | Assessment conversation, teacher-persona choice, extracted profile |
| 250–408 | 0:08.3–0:13.6 | Course plan — concrete knowledge points, a revised day, stretch + time |
| 408–560 | 0:13.6–0:18.7 | Coaching — one correction: original, fixed, and why |
| 560–710 | 0:18.7–0:23.7 | Skill profile — five meters and the settings computed for today |
| 710–840 | 0:23.7–0:28 | `/review` — flashcard reveal and the four SM-2 ratings |
| 840–900 | 0:28–0:30 | Title card, feature chips, run command |

1920×1080 at 30fps = 900 frames.

## Every claim on screen is real

The copy is taken from the application's own code rather than invented:

| On screen | Source |
|---|---|
| Four teacher personas + blurbs | `src/persona.py` (`PERSONA_PRESETS`) |
| `original → corrected / why` correction shape | `src/daily_coach.py` |
| Five skill dimensions | `src/dynamic_profile.py` (`SkillScores`) |
| "Today the coach was set to" block | `src/coach_policy.py` (`SessionDirectives.render`) |
| `1 Again / 2 Hard / 3 Good / 4 Easy` | `src/srs.py` (`RATING_LABELS`) |
| "revised" day badge | `revise_plan_tail()` rewriting remaining days |
| "the model guessed *beginner* — the scores overrode it" | the real behaviour: `recommended_difficulty` from the profile is overridden by the computed average |
| "next review in 1 day" | actual SM-2 result for a first card rated Good |

## Run it

```bash
npm install
npm run typecheck

# quick layout check — render stills BEFORE the full film
npx remotion still Promo out/check.png --frame=635

npm run render          # out/englishcoach-promo.mp4
npm run studio          # interactive
```

**Render stills before rendering 900 frames.** Three real bugs in this project
were only visible that way:

1. `Scene` originally called `useCurrentFrame()` **outside** its own
   `<Sequence>`, so it read the global frame and compared it against each
   scene's short local duration. Every scene faded straight to `opacity: 0`
   and the film came out near-black for its full length, while the renderer
   still reported success. The fix is `useCurrentFrame() - from`.
2. A regex edit of `Promo.tsx` unbalanced the JSX nesting. `remotion still`
   then failed *silently*, leaving stale PNGs from the previous run, which
   looked exactly like a rendering bug.
3. The review scene flipped the flashcard back to its front after grading, so
   it briefly showed "unrevealed card + already rated".

## Environment notes for this machine

- npm registry is set to `https://registry.npmmirror.com`;
  `registry.npmjs.org` is unreachable here.
- `remotion.config.ts` points `Config.setBrowserExecutable` at the system
  Chrome. Remotion downloads its own Chrome from GitHub, and GitHub is blocked
  on this network.
- `node_modules/@remotion/compositor-win32-x64-msvc/remotion.exe` is a
  purpose-built compositor, **not** a general ffmpeg CLI — it rejects ordinary
  ffmpeg arguments with `{"error":"invalid number at line 1 column 2"}`. To
  extract frames from a finished file, install `@ffmpeg-installer/ffmpeg`,
  which ships the binary inside the npm tarball (so no GitHub download).
