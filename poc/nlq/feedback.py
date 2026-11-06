"""Local append-only storage for opt-in NLQ feedback sessions."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
from threading import Lock
from uuid import uuid4


_SESSION_ID = re.compile(r"^[0-9a-f]{32}$")


class FeedbackError(ValueError):
    pass


class FeedbackStore:
    def __init__(self, directory: Path):
        self.directory = Path(directory)
        self._lock = Lock()

    def _paths(self, session_id: str) -> tuple[Path, Path]:
        if not isinstance(session_id, str) or not _SESSION_ID.fullmatch(session_id):
            raise FeedbackError("Invalid feedback session.")
        return (self.directory / f"{session_id}.jsonl",
                self.directory / f"{session_id}.json")

    def start(self) -> str:
        with self._lock:
            self.directory.mkdir(parents=True, exist_ok=True)
            session_id = uuid4().hex
            records, state = self._paths(session_id)
            # Create the append-only stream first; report success only when both
            # durable session files have been created.
            with records.open("xb") as stream:
                stream.flush()
                os.fsync(stream.fileno())
            self._write_state(state, {"active": True})
            return session_id

    def status(self, session_id: str) -> bool:
        records, state = self._paths(session_id)
        try:
            metadata = json.loads(state.read_text(encoding="utf-8"))
            return records.is_file() and metadata.get("active") is True
        except (OSError, ValueError, AttributeError):
            return False

    def stop(self, session_id: str) -> None:
        _, state = self._paths(session_id)
        with self._lock:
            try:
                metadata = json.loads(state.read_text(encoding="utf-8"))
            except (OSError, ValueError) as error:
                raise FeedbackError("Feedback session was not found.") from error
            if not (self.directory / f"{session_id}.jsonl").is_file():
                raise FeedbackError("Feedback session was not found.")
            metadata["active"] = False
            self._write_state(state, metadata)

    def append(self, session_id: str, *, question: str, expected: str,
               actual: str, correct: bool) -> None:
        records, state = self._paths(session_id)
        if not self.status(session_id):
            raise FeedbackError("Feedback session is not active.")
        if not all(isinstance(value, str) for value in (question, expected, actual)):
            raise FeedbackError("Feedback fields must be text.")
        if not question.strip() or len(question) > 2000 or len(expected) > 10000 or len(actual) > 50000:
            raise FeedbackError("Feedback fields are empty or exceed the allowed length.")
        if type(correct) is not bool:
            raise FeedbackError("Adequacy must be a boolean.")
        if correct and expected:
            raise FeedbackError("Expected answer must be empty when the response was adequate.")
        if not correct and not expected.strip():
            raise FeedbackError("Enter the expected answer when the response was inadequate.")
        record = {"question": question, "expected": expected,
                  "actual": actual, "correct": correct}
        line = (json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        with self._lock:
            # Recheck while serialized against stop, so no record can be
            # acknowledged after a stop transition.
            try:
                active = json.loads(state.read_text(encoding="utf-8")).get("active") is True
            except (OSError, ValueError, AttributeError):
                active = False
            if not active or not records.is_file():
                raise FeedbackError("Feedback session is not active.")
            fd = os.open(records, os.O_WRONLY | os.O_APPEND)
            try:
                with os.fdopen(fd, "ab", closefd=False) as stream:
                    stream.write(line)
                    stream.flush()
                    os.fsync(stream.fileno())
            finally:
                os.close(fd)

    @staticmethod
    def _write_state(path: Path, state: dict) -> None:
        temporary = path.with_suffix(".json.tmp")
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(state, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
