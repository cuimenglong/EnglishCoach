"""Headless smoke test: every screen must still mount after the P0 fixes."""
import sys, os, json, pathlib, tempfile, asyncio

TMP = pathlib.Path(tempfile.mkdtemp(prefix="ecoach_smoke_"))
# project root is the parent of tests/
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from textual.app import App

import src.utils as utils
utils.DATA_DIR = TMP; utils.APP_ROOT = TMP
import src.config as cfgmod;      cfgmod.APP_ROOT = TMP
import src.sessions as sessmod;   sessmod.DATA_DIR = TMP; sessmod.SESSION_FILE = TMP/"session.json"
import src.knowledge as K;        K.DATA_DIR = TMP; K.DB_PATH = TMP/"knowledge.db"
import src.dynamic_profile as dp; dp.PROFILE_PATH = TMP/"dynamic_profile.json"

from src.app import EnglishCoachApp
from src.config import Config
from src.course_plan import PLAN_SCHEMA_VERSION

PLAN = {"total_days": 14, "schema_version": PLAN_SCHEMA_VERSION, "days": [
    {"day": d, "topic": f"Topic {d}", "focus": "f",
     "exercise_types": ["free_writing"], "vocab_theme": "v",
     "knowledge_points": [{"id": "kp1", "title": f"Knowledge point {d}",
                           "detail": "learn to do X", "example": "e.g. this"}],
     "extension": "stretch idea", "estimated_minutes": 20}
    for d in range(1, 15)]}

# Without a plan the app still mounts CoachScreen, so assert the plan really
# loaded -- otherwise this case silently tests the no-plan fallback path.
PERSONA = {"level": "B1", "study_days": 14, "last_completed_day": None,
           "persona": {"preset": "friendly", "warmth": 5, "strictness": 2,
                       "verbosity": "balanced", "correction_style": "gentle",
                       "accent": "neutral", "free_text": ""}}

CASES = [
    ("settings (no api key)", dict(openai_api_key=""), {}),
    ("assessment screen", dict(openai_api_key="sk-test"),
     {}),
    ("coach screen (with plan + persona)", dict(openai_api_key="sk-test"),
     {"user_profile.json": PERSONA, "course_plan.json": PLAN}),
    ("coach screen (mid-plan)", dict(openai_api_key="sk-test"),
     {"user_profile.json": {**PERSONA, "last_completed_day": 6},
      "course_plan.json": PLAN}),
    ("coach screen (stale v1 plan -> regenerates)", dict(openai_api_key="sk-test"),
     {"user_profile.json": PERSONA,
      "course_plan.json": {"total_days": 14, "days": [
          {"day": d, "topic": "old", "focus": "f",
           "exercise_types": ["x"], "vocab_theme": "v"} for d in range(1, 15)]}}),
]

async def main():
    print("textual", __import__("textual").__version__)
    fails = 0
    for name, cfg, files in CASES:
        for f in TMP.glob("*"):
            if f.is_file(): f.unlink()
        for fn, data in files.items():
            (TMP/fn).write_text(json.dumps(data), encoding="utf-8")
        app = EnglishCoachApp()
        app.config = Config(model_name="gpt-4o",
                            base_url="https://api.openai.com/v1",
                            temperature=0.7, **cfg)
        try:
            async with app.run_test() as pilot:
                await pilot.pause()
                await asyncio.sleep(0.3)
                await pilot.pause()
                screen = type(app.screen).__name__
                if name.startswith("coach screen (with plan") or name.startswith("coach screen (mid-plan"):
                    loaded = app.screen.plan
                    if loaded is None:
                        print(f"  [FAIL] {name}: mounted but plan did NOT load "
                              f"(system prompt fell back to the no-plan path)")
                        fails += 1
                        continue
                    if not app.screen.today_plan.knowledge_points:
                        print(f"  [FAIL] {name}: today's plan has no knowledge points")
                        fails += 1
                        continue
                    if "COACHING PERSONA" not in app.screen.system_prompt:
                        print(f"  [FAIL] {name}: persona missing from system prompt")
                        fails += 1
                        continue
                    if "KNOWLEDGE POINTS" not in app.screen.system_prompt:
                        print(f"  [FAIL] {name}: knowledge points missing from system prompt")
                        fails += 1
                        continue
                print(f"  [OK  ] {name}: {screen}")
        except Exception as e:
            fails += 1
            print(f"  [FAIL] {name}: {type(e).__name__}: {e}")
    return fails

fails = asyncio.run(main())

# Every sub-screen the coach can push must render a frame. A screen whose
# render() returns None blows up here rather than silently on screen.
import importlib
from src.course_plan import CoursePlan, DailyPlan
from src.dynamic_profile import DynamicProfile
from src.coach_policy import build_session_directives

_plan_obj = CoursePlan(
    total_days=PLAN["total_days"],
    schema_version=PLAN["schema_version"],
    days=[DailyPlan(**d) for d in PLAN["days"]],
)
_prof = DynamicProfile()
SUB_SCREENS = [
    ("src.tui.screens.vocabulary_screen", "VocabularyScreen", ()),
    ("src.tui.screens.course_plan_screen", "CoursePlanScreen", (_plan_obj,)),
    ("src.tui.screens.history_screen", "HistoryScreen", ()),
    ("src.tui.screens.review_screen", "ReviewScreen", ()),
    ("src.tui.screens.profile_screen", "ProfileScreen",
     (_prof, build_session_directives(_prof, None))),
]

for module_name, cls_name, args in SUB_SCREENS:
    try:
        cls = getattr(importlib.import_module(module_name), cls_name)

        class _Sub(App):
            # Only the stylesheet is needed; the app's navigation state machine
            # would push CoachScreen on top of the screen under test.
            CSS = EnglishCoachApp.CSS

            def on_mount(self):
                from src.knowledge import init_db
                init_db()
                self.push_screen(cls(*args))

        async def _run_sub():
            app = _Sub()
            app.config = Config(openai_api_key="sk-test")
            async with app.run_test() as pilot:
                await pilot.pause()
                await asyncio.sleep(0.2)
                await pilot.pause()
                return type(app.screen).__name__

        got = asyncio.run(_run_sub())
        if got != cls_name:
            print(f"  [FAIL] {cls_name}: landed on {got}")
            fails += 1
        else:
            print(f"  [OK  ] {cls_name}: rendered")
    except Exception as e:
        fails += 1
        print(f"  [FAIL] {cls_name}: {type(e).__name__}: {str(e)[:70]}")

print("=" * 60)
print("smoke test:", "ALL PASS" if not fails else f"{fails} FAILURE(S)")
sys.exit(1 if fails else 0)
