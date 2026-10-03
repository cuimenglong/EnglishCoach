"""Headless smoke test: every screen must still mount after the P0 fixes."""
import sys, os, json, pathlib, tempfile, asyncio

TMP = pathlib.Path(tempfile.mkdtemp(prefix="ecoach_smoke_"))
# project root is the parent of tests/
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import src.utils as utils
utils.DATA_DIR = TMP; utils.APP_ROOT = TMP
import src.config as cfgmod;      cfgmod.APP_ROOT = TMP
import src.sessions as sessmod;   sessmod.DATA_DIR = TMP; sessmod.SESSION_FILE = TMP/"session.json"
import src.knowledge as K;        K.DATA_DIR = TMP; K.DB_PATH = TMP/"knowledge.db"
import src.dynamic_profile as dp; dp.PROFILE_PATH = TMP/"dynamic_profile.json"

from src.app import EnglishCoachApp
from src.config import Config

PLAN = {"total_days": 14, "days": [
    {"day": d, "topic": f"Topic {d}", "focus": "f",
     "exercise_types": ["free_writing"], "vocab_theme": "v"} for d in range(1, 15)]}

CASES = [
    ("settings (no api key)", dict(openai_api_key=""), {}),
    ("assessment screen", dict(openai_api_key="sk-test"),
     {}),
    ("coach screen", dict(openai_api_key="sk-test"),
     {"user_profile.json": {"level": "B1", "study_days": 14, "last_completed_day": None},
      "course_plan.json": PLAN}),
    ("coach screen (mid-plan)", dict(openai_api_key="sk-test"),
     {"user_profile.json": {"level": "B1", "study_days": 14, "last_completed_day": 6},
      "course_plan.json": PLAN}),
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
                print(f"  [OK  ] {name}: {type(app.screen).__name__}")
        except Exception as e:
            fails += 1
            print(f"  [FAIL] {name}: {type(e).__name__}: {e}")
    return fails

fails = asyncio.run(main())
print("=" * 60)
print("smoke test:", "ALL PASS" if not fails else f"{fails} FAILURE(S)")
sys.exit(1 if fails else 0)
