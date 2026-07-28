import json
from datetime import date

from .utils import DATA_DIR, read_json, write_json


SESSION_FILE = DATA_DIR / "session.json"


class SessionManager:
    STAGE_ASSESSMENT = "assessment"
    STAGE_PLANNING = "planning"
    STAGE_TRAINING = "training"

    def __init__(self):
        self.stage: str = self.STAGE_ASSESSMENT
        self.current_day: int = 1
        self.total_days: int = 14
        self.assessment_history: list[dict] = []
        self.training_history: list[dict] = []
        self.last_session_date: str = ""
        self._load()

    def _load(self):
        if SESSION_FILE.exists():
            try:
                data = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
                self.stage = data.get("stage", self.STAGE_ASSESSMENT)
                self.current_day = data.get("current_day", 1)
                self.total_days = data.get("total_days", 14)
                self.assessment_history = data.get("assessment_history", [])
                self.training_history = data.get("training_history", [])
                self.last_session_date = data.get("last_session_date", "")
            except (json.JSONDecodeError, KeyError):
                pass

        user_profile = read_json("user_profile.json")
        course_plan = read_json("course_plan.json")

        if not user_profile:
            self.stage = self.STAGE_ASSESSMENT
        elif not course_plan:
            self.stage = self.STAGE_PLANNING
        else:
            self.stage = self.STAGE_TRAINING
            if course_plan.get("total_days"):
                self.total_days = course_plan["total_days"]

            # Progress is completion-based: next day after last completed day.
            last_completed = user_profile.get("last_completed_day")
            if last_completed is not None:
                try:
                    last_completed = int(last_completed)
                except (TypeError, ValueError):
                    last_completed = 0
                self.current_day = min(max(last_completed + 1, 1), self.total_days)
            else:
                # Keep any previously saved day, but never go below 1.
                self.current_day = max(1, min(self.current_day or 1, self.total_days))

        self._check_day_change()

    def _check_day_change(self):
        """Clear unfinished same-day history only when the calendar day changes.

        Day index itself is driven by last_completed_day, not by date gaps.
        """
        today = date.today().isoformat()
        if self.last_session_date and self.last_session_date != today:
            self.training_history = []
            self.last_session_date = today

    def save(self):
        today = date.today().isoformat()
        self.last_session_date = today
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "stage": self.stage,
            "current_day": self.current_day,
            "total_days": self.total_days,
            "assessment_history": self.assessment_history,
            "training_history": self.training_history,
            "last_session_date": self.last_session_date,
        }
        SESSION_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def reset_training(self):
        self.training_history = []
        self.save()

    def is_complete(self) -> bool:
        user_profile = read_json("user_profile.json") or {}
        last_completed = user_profile.get("last_completed_day", 0) or 0
        return int(last_completed) >= self.total_days

    def advance_day(self):
        if self.current_day < self.total_days:
            self.current_day += 1
            self.reset_training()
            self.save()
