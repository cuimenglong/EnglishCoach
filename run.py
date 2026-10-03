"""Launcher script for the English Coach application.

Works both as source (python run.py) and as frozen PyInstaller exe.
"""
import sys
import os
import logging


def main():
    # Determine project root
    if getattr(sys, "frozen", False):
        project_root = os.path.dirname(os.path.abspath(sys.executable))
    else:
        project_root = os.path.dirname(os.path.abspath(__file__))

    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    os.chdir(project_root)

    # `EnglishCoach.exe --selftest` verifies the frozen build actually contains
    # the expected features, with no terminal or API key needed.
    if "--selftest" in sys.argv:
        return selftest()

    # Logs go next to the app so a failed LLM call is diagnosable after the fact.
    log_dir = os.path.join(project_root, "data")
    os.makedirs(log_dir, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(os.path.join(log_dir, "englishcoach.log"), encoding="utf-8"),
        ],
    )

    from src.app import EnglishCoachApp

    app = EnglishCoachApp()
    app.run()


def selftest() -> int:
    """Exercise the real code paths and report what this build contains.

    Each check calls the actual code, so this is a build gate rather than a
    claim. Exits non-zero if anything is missing or broken.
    """
    import importlib
    import platform

    print("EnglishCoach selftest")
    print(f"  frozen : {getattr(sys, 'frozen', False)}")
    print(f"  python : {platform.python_version()}")
    print(f"  exe    : {os.path.abspath(sys.executable)}")
    print()

    failures = []

    def check(name, fn):
        try:
            detail = fn()
            print(f"  [OK  ] {name}" + (f" -- {detail}" if detail else ""))
        except Exception as exc:
            failures.append(name)
            print(f"  [FAIL] {name} -- {type(exc).__name__}: {exc}")

    # -- P0 regressions -------------------------------------------------
    def p0_profile_update():
        from src.dynamic_profile import (
            DynamicProfile, SkillScores, apply_profile_update, format_profile_for_prompt
        )
        merged = apply_profile_update(DynamicProfile(), {
            "cefr_level": "B1",
            "skill_scores": {"grammar": 6, "vocabulary": 5, "sentence_structure": 6,
                             "fluency": 5, "accuracy": 4},
        })
        if not isinstance(merged.skill_scores, SkillScores):
            raise AssertionError("skill_scores was not re-validated into a model")
        format_profile_for_prompt(merged)
        return "nested dict re-validated into SkillScores"

    def p0_fts_hardening():
        from src import knowledge as K
        K.init_db()
        hostile = ['"x', "a AND OR", "NOT", "*", "x(", "NEAR(", "col:val", "-minus"]
        for q in hostile:
            K.search_vocabulary(q)
            K._handle_search(q)
        return f"{len(hostile)} hostile queries survived"

    def p0_review_queue():
        from src.knowledge import add_vocabulary, get_due_cards, review_stats, delete_vocabulary
        new_id = add_vocabulary("selftest manual", "m", "", "t", source="manual")
        auto_id = add_vocabulary("selftest auto", "m", "", "t", source="coach")
        due_ids = {c.id for c in get_due_cards()}
        if new_id not in due_ids:
            raise AssertionError("manual /save entry should be due immediately")
        if auto_id in due_ids:
            raise AssertionError("coach-saved entry must not enter the queue unasked")
        due = review_stats()["due"]
        # Do not leave test rows in the learner's real vocabulary bank.
        for row_id in (new_id, auto_id):
            delete_vocabulary(row_id)
        return f"{due} due, auto-save correctly held back"

    # -- Phase 1 --------------------------------------------------------
    def phase1_persona():
        from src.persona import (
            PERSONA_PRESETS, persona_from_preset, render_persona_prompt
        )
        examiner = render_persona_prompt(persona_from_preset("examiner"))
        friendly = render_persona_prompt(persona_from_preset("friendly"))
        if "COACHING PERSONA" not in examiner:
            raise AssertionError("persona fragment not rendered")
        if examiner == friendly:
            raise AssertionError("persona axes do not change the prompt")
        return f"{len(PERSONA_PRESETS)} presets, fragments differ"

    # -- Phase 2 --------------------------------------------------------
    def phase2_plan():
        from src.course_plan import PLAN_SCHEMA_VERSION, build_plan_from_days
        plan = build_plan_from_days([
            {"day": i, "topic": f"T{i}", "focus": "f", "vocab_theme": "v",
             "exercise_types": ["gap_fill"],
             "knowledge_points": [{"title": f"KP{i}", "detail": "d"}],
             "extension": "stretch", "estimated_minutes": 20}
            for i in range(1, 4)
        ])
        if plan.schema_version != PLAN_SCHEMA_VERSION:
            raise AssertionError("plan not stamped with the current schema")
        if plan.days[0].knowledge_points[0].title != "KP1":
            raise AssertionError("knowledge points missing")
        return f"schema v{plan.schema_version}, knowledge points present"

    # -- Phase 3 --------------------------------------------------------
    def phase3_decision_engine():
        from src.dynamic_profile import DynamicProfile, SkillScores
        from src.coach_policy import build_session_directives
        profile = DynamicProfile(
            skill_scores=SkillScores(grammar=6, vocabulary=5, sentence_structure=6,
                                     fluency=5, accuracy=4),
            recommended_difficulty="beginner",
        )
        directives = build_session_directives(profile, None)
        if directives.difficulty != "intermediate":
            raise AssertionError(
                f"scores average 5.2 so difficulty must be intermediate, "
                f"got {directives.difficulty!r}")
        if directives.priority_dimension != "accuracy":
            raise AssertionError(
                f"accuracy is lowest at 4/10, got {directives.priority_dimension!r}")
        return (f"difficulty={directives.difficulty} (model said beginner), "
                f"priority={directives.priority_dimension}, "
                f"target={directives.target_exchanges} exchanges")

    # -- Phase 4 --------------------------------------------------------
    def phase4_scheduler():
        from src.srs import compute_review, RATING_GOOD, RATING_AGAIN
        first = compute_review(reps=0, lapses=0, ease=2.5, interval_days=0.0,
                               rating=RATING_GOOD)
        failed = compute_review(reps=1, lapses=0, ease=2.5, interval_days=1.0,
                                rating=RATING_AGAIN)
        if first["state"] != "learning" or failed["state"] != "relearning":
            raise AssertionError("SM-2 state machine did not advance correctly")
        return f"GOOD->{first['interval_days']}d, AGAIN->due today"

    # -- Phase 5 --------------------------------------------------------
    def phase5_markdown():
        from rich.markdown import Markdown
        from src.tui.widgets.chat_widgets import format_coach_message
        from src import daily_coach
        if not isinstance(format_coach_message("**hi**"), Markdown):
            raise AssertionError("coach replies are not rendered as Markdown")
        prompts = "".join(v for v in vars(daily_coach).values() if isinstance(v, str))
        if "Do NOT use Markdown" in prompts:
            raise AssertionError("a prompt still forbids Markdown")
        return "Markdown enabled and no longer forbidden"

    def screens_renderable():
        from textual.widget import Widget
        modules = {
            "src.tui.screens.settings_screen": "SettingsScreen",
            "src.tui.screens.assessment_screen": "AssessmentScreen",
            "src.tui.screens.coach_screen": "CoachScreen",
            "src.tui.screens.vocabulary_screen": "VocabularyScreen",
            "src.tui.screens.course_plan_screen": "CoursePlanScreen",
            "src.tui.screens.history_screen": "HistoryScreen",
            "src.tui.screens.review_screen": "ReviewScreen",
            "src.tui.screens.profile_screen": "ProfileScreen",
        }
        for module_name, class_name in modules.items():
            cls = getattr(importlib.import_module(module_name), class_name)
            # A screen that shadows Widget._render cannot draw a frame at all.
            if cls._render is not Widget._render:
                raise AssertionError(f"{class_name} shadows Widget._render()")
        return f"{len(modules)} screens, no render-hook collisions"

    check("P0  /summary profile update", p0_profile_update)
    check("P0  FTS5 query hardening", p0_fts_hardening)
    check("P0  review queue integrity", p0_review_queue)
    check("P1  coach persona", phase1_persona)
    check("P2  knowledge-point plan", phase2_plan)
    check("P3  decision engine", phase3_decision_engine)
    check("P4  SM-2 scheduler", phase4_scheduler)
    check("P5  markdown rendering", phase5_markdown)
    check("All screens importable", screens_renderable)

    print()
    if failures:
        print(f"RESULT: FAILED ({len(failures)}): {', '.join(failures)}")
        return 1
    print("RESULT: OK -- this build contains the P0 fixes and Phase 1-5 features")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
