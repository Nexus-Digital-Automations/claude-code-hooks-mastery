#!/usr/bin/env python3
"""
Tests for hooks/utils/deepseek_verifier.py and the stop.py helpers
format_evidence_display and the DeepSeek gate logic.

Run with: python -m pytest tests/test_deepseek_verifier.py -v
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import urllib.error

# Add hooks directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))


# ─── deepseek_verifier ───────────────────────────────────────────────────────

class TestVerifyWithDeepseekSkipsWhenNoKey:
    def test_no_api_key_returns_approved_skipped(self, monkeypatch):
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        from utils.deepseek_verifier import verify_with_deepseek
        result = verify_with_deepseek({})
        assert result["approved"] is True
        assert result["skipped"] is True
        assert "DEEPSEEK_API_KEY" in result["skip_reason"]

    def test_empty_api_key_returns_skipped(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "")
        from utils.deepseek_verifier import verify_with_deepseek
        result = verify_with_deepseek({})
        assert result["skipped"] is True


class TestVerifyWithDeepseekApproval:
    """Tests using a mocked HTTP call."""

    def _make_response(self, payload: dict) -> MagicMock:
        """Build a mock urllib response that returns payload as JSON."""
        content = json.dumps({
            "choices": [{
                "message": {
                    "content": json.dumps(payload)
                }
            }]
        }).encode("utf-8")
        mock_resp = MagicMock()
        mock_resp.read.return_value = content
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    def test_approved_true_returns_approved(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-key")
        mock_resp = self._make_response({
            "approved": True,
            "verdict": "Evidence looks genuine.",
            "suspicious_steps": [],
            "instructions": "",
        })
        with patch("urllib.request.urlopen", return_value=mock_resp):
            from utils import deepseek_verifier
            import importlib
            importlib.reload(deepseek_verifier)
            result = deepseek_verifier.verify_with_deepseek({"tests": {"status": "done", "evidence": "47 passed in 3.2s"}})
        assert result["approved"] is True
        assert result["skipped"] is False
        assert result["skip_reason"] == ""
        assert result["verdict"] == "Evidence looks genuine."

    def test_approved_false_returns_rejected(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-key")
        mock_resp = self._make_response({
            "approved": False,
            "verdict": "Evidence is too vague.",
            "suspicious_steps": ["tests", "build"],
            "instructions": "Re-run pytest and paste actual output.",
        })
        with patch("urllib.request.urlopen", return_value=mock_resp):
            from utils import deepseek_verifier
            import importlib
            importlib.reload(deepseek_verifier)
            result = deepseek_verifier.verify_with_deepseek({"tests": {"status": "done", "evidence": "ok"}})
        assert result["approved"] is False
        assert result["skipped"] is False
        assert "tests" in result["suspicious_steps"]
        assert "build" in result["suspicious_steps"]
        assert "pytest" in result["instructions"]


class TestVerifyWithDeepseekErrorHandling:
    def test_http_error_returns_skipped(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-key")
        with patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError(
            url="", code=429, msg="Too Many Requests", hdrs=None, fp=None
        )):
            from utils import deepseek_verifier
            import importlib
            importlib.reload(deepseek_verifier)
            result = deepseek_verifier.verify_with_deepseek({})
        assert result["approved"] is True
        assert result["skipped"] is True
        assert "429" in result["skip_reason"]

    def test_timeout_returns_skipped(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-key")
        with patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")):
            from utils import deepseek_verifier
            import importlib
            importlib.reload(deepseek_verifier)
            result = deepseek_verifier.verify_with_deepseek({})
        assert result["approved"] is True
        assert result["skipped"] is True
        assert "timeout" in result["skip_reason"].lower()

    def test_url_error_timeout_variant_returns_skipped(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-key")
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("timed out")):
            from utils import deepseek_verifier
            import importlib
            importlib.reload(deepseek_verifier)
            result = deepseek_verifier.verify_with_deepseek({})
        assert result["approved"] is True
        assert result["skipped"] is True

    def test_generic_exception_returns_skipped(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-key")
        with patch("urllib.request.urlopen", side_effect=RuntimeError("boom")):
            from utils import deepseek_verifier
            import importlib
            importlib.reload(deepseek_verifier)
            result = deepseek_verifier.verify_with_deepseek({})
        assert result["approved"] is True
        assert result["skipped"] is True
        assert "verifier error" in result["skip_reason"]

    def test_json_parse_failure_with_suspicious_keyword_blocks(self, monkeypatch):
        """If DeepSeek returns non-JSON but text contains 'suspicious', treat as rejected."""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-key")
        raw_api_response = json.dumps({
            "choices": [{"message": {"content": "The evidence is suspicious and rejected."}}]
        }).encode("utf-8")
        mock_resp = MagicMock()
        mock_resp.read.return_value = raw_api_response
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            from utils import deepseek_verifier
            import importlib
            importlib.reload(deepseek_verifier)
            result = deepseek_verifier.verify_with_deepseek({})
        assert result["approved"] is False
        assert result["skipped"] is False

    def test_json_parse_failure_without_keywords_skips(self, monkeypatch):
        """If DeepSeek returns non-JSON and no suspicious keywords, skip gracefully."""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-key")
        raw_api_response = json.dumps({
            "choices": [{"message": {"content": "I have reviewed the evidence carefully."}}]
        }).encode("utf-8")
        mock_resp = MagicMock()
        mock_resp.read.return_value = raw_api_response
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            from utils import deepseek_verifier
            import importlib
            importlib.reload(deepseek_verifier)
            result = deepseek_verifier.verify_with_deepseek({})
        assert result["approved"] is True
        assert result["skipped"] is True


class TestBuildUserMessage:
    def test_all_checks_present_in_message(self):
        from utils.deepseek_verifier import _build_user_message, _VR_CHECKS_ORDER
        checks = {
            key: {"status": "done", "evidence": f"evidence for {key}"}
            for key, _ in _VR_CHECKS_ORDER
        }
        msg = _build_user_message(checks)
        for key, label in _VR_CHECKS_ORDER:
            assert label in msg
            assert f"evidence for {key}" in msg

    def test_skipped_check_shows_skip_reason(self):
        from utils.deepseek_verifier import _build_user_message
        checks = {"tests": {"status": "skipped", "skip_reason": "no test suite in this project"}}
        msg = _build_user_message(checks)
        assert "no test suite in this project" in msg
        assert "Skip reason" in msg

    def test_pending_check_shows_none_completed(self):
        from utils.deepseek_verifier import _build_user_message
        checks = {}
        msg = _build_user_message(checks)
        assert "never completed" in msg

    def test_evidence_truncated_to_800_chars(self):
        from utils.deepseek_verifier import _build_user_message
        long_evidence = "x" * 2000
        checks = {"tests": {"status": "done", "evidence": long_evidence}}
        msg = _build_user_message(checks)
        # The evidence repr is inside the message — length should not exceed truncate + overhead
        assert long_evidence not in msg  # Full string should not appear


class TestReturnStructure:
    """Verify all return keys are always present."""

    def test_skipped_has_all_keys(self, monkeypatch):
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        from utils import deepseek_verifier
        import importlib
        importlib.reload(deepseek_verifier)
        result = deepseek_verifier.verify_with_deepseek({})
        for key in ("approved", "verdict", "suspicious_steps", "instructions", "skipped", "skip_reason"):
            assert key in result, f"Missing key: {key}"

    def test_approved_result_has_all_keys(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-key")
        content = json.dumps({
            "choices": [{"message": {"content": json.dumps({
                "approved": True, "verdict": "ok", "suspicious_steps": [], "instructions": ""
            })}}]
        }).encode("utf-8")
        mock_resp = MagicMock()
        mock_resp.read.return_value = content
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            from utils import deepseek_verifier
            import importlib
            importlib.reload(deepseek_verifier)
            result = deepseek_verifier.verify_with_deepseek({})
        for key in ("approved", "verdict", "suspicious_steps", "instructions", "skipped", "skip_reason"):
            assert key in result, f"Missing key: {key}"


# ─── format_evidence_display (stop.py helper) ────────────────────────────────

class TestFormatEvidenceDisplay:
    def _import(self):
        import importlib
        import stop
        importlib.reload(stop)
        return stop.format_evidence_display

    def test_empty_done_items_shows_header(self):
        fn = self._import()
        out = fn([], {})
        assert "VERIFICATION EVIDENCE SUMMARY" in out

    def test_done_item_shows_evidence(self):
        fn = self._import()
        done_items = [("tests", "TESTS", "done", "12:34", "47 passed")]
        checks = {"tests": {"status": "done", "evidence": "===== 47 passed in 3.21s ====="}}
        out = fn(done_items, checks)
        assert "47 passed in 3.21s" in out
        assert "Command output" in out
        assert "✅" in out

    def test_skipped_item_shows_skip_reason(self):
        fn = self._import()
        done_items = [("tests", "TESTS", "skipped", "12:34", "no tests")]
        checks = {"tests": {"status": "skipped", "skip_reason": "no test framework present"}}
        out = fn(done_items, checks)
        assert "no test framework present" in out
        assert "Skip reason" in out
        assert "⏭" in out

    def test_long_evidence_is_truncated(self):
        fn = self._import()
        long_ev = "A" * 2000
        done_items = [("tests", "TESTS", "done", "12:34", long_ev[:70])]
        checks = {"tests": {"status": "done", "evidence": long_ev}}
        out = fn(done_items, checks)
        assert "more chars truncated" in out
        assert "A" * 501 not in out  # Should be truncated at 500

    def test_missing_evidence_shows_none_recorded(self):
        fn = self._import()
        done_items = [("tests", "TESTS", "done", "12:34", "")]
        checks = {"tests": {"status": "done", "evidence": None}}
        out = fn(done_items, checks)
        assert "(none recorded)" in out

    def test_step_numbers_increment(self):
        fn = self._import()
        done_items = [
            ("tests", "TESTS", "done", "12:34", "ok"),
            ("build", "BUILD", "done", "12:35", "ok"),
        ]
        checks = {
            "tests": {"status": "done", "evidence": "tests ok"},
            "build": {"status": "done", "evidence": "build ok"},
        }
        out = fn(done_items, checks)
        assert "Step 1:" in out
        assert "Step 2:" in out


# ─── Multi-turn conversation tests ───────────────────────────────────────────

class TestMultiTurnConversation:
    """Tests for the new multi-turn conversational DeepSeek reviewer."""

    def _make_api_response(self, content: str) -> MagicMock:
        """Build a mock urllib response returning raw text content."""
        raw = json.dumps({
            "choices": [{"message": {"content": content}}]
        }).encode("utf-8")
        mock_resp = MagicMock()
        mock_resp.read.return_value = raw
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    def test_question_response_returns_pending(self, monkeypatch, tmp_path):
        """When DeepSeek responds with QUESTION:, result has pending=True."""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-key")
        mock_resp = self._make_api_response(
            "QUESTION: Did you run pytest before or after editing stop.py?"
        )
        with patch("urllib.request.urlopen", return_value=mock_resp):
            from utils import deepseek_verifier
            import importlib
            importlib.reload(deepseek_verifier)
            state_file = tmp_path / "state.json"
            result = deepseek_verifier.verify_with_deepseek(
                {"tests": {"status": "done", "evidence": "ok"}},
                state_file=state_file,
            )
        assert result["pending"] is True
        assert "pytest" in result["questions"].lower() or "before" in result["questions"].lower()
        assert result["approved"] is False
        assert result["skipped"] is False

    def test_state_file_saved_on_question(self, monkeypatch, tmp_path):
        """State file is written when DeepSeek asks a question."""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-key")
        mock_resp = self._make_api_response("QUESTION: Did you run tests?")
        with patch("urllib.request.urlopen", return_value=mock_resp):
            from utils import deepseek_verifier
            import importlib
            importlib.reload(deepseek_verifier)
            state_file = tmp_path / "state.json"
            deepseek_verifier.verify_with_deepseek({}, state_file=state_file)
        assert state_file.exists()
        data = json.loads(state_file.read_text())
        msgs = data.get("messages", [])
        assert len(msgs) >= 2  # Initial user message + assistant question
        last_asst = next(m for m in reversed(msgs) if m["role"] == "assistant")
        assert last_asst["content"].startswith("QUESTION:")

    def test_conversation_continues_with_state(self, monkeypatch, tmp_path):
        """When state file has prior history, second call continues from it."""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-key")

        # Pre-seed state: a question was asked, Claude answered
        state_file = tmp_path / "state.json"
        pre_state = {
            "messages": [
                {"role": "user", "content": "...initial evidence..."},
                {"role": "assistant", "content": "QUESTION: Did you run pytest?"},
                {"role": "user", "content": "Yes, I ran pytest after the edit. 9 passed."},
            ]
        }
        state_file.write_text(json.dumps(pre_state))

        # DeepSeek now approves
        verdict = json.dumps({
            "approved": True,
            "verdict": "Evidence is genuine after clarification.",
            "suspicious_steps": [],
            "instructions": "",
        })
        mock_resp = self._make_api_response(verdict)

        messages_sent = []

        def capture_urlopen(req, timeout):
            import json as _json
            body = _json.loads(req.data.decode())
            messages_sent.extend(body["messages"])
            return mock_resp

        with patch("urllib.request.urlopen", side_effect=capture_urlopen):
            from utils import deepseek_verifier
            import importlib
            importlib.reload(deepseek_verifier)
            result = deepseek_verifier.verify_with_deepseek({}, state_file=state_file)

        assert result["approved"] is True
        assert result["pending"] is False
        # Verify the prior conversation was included in the API call
        user_contents = [m["content"] for m in messages_sent if m["role"] == "user"]
        assert any("9 passed" in c for c in user_contents)

    def test_approved_on_followup(self, monkeypatch, tmp_path):
        """End-to-end: first turn asks a question, second turn approves."""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-key")

        # First call: question
        state_file = tmp_path / "state.json"
        question_resp = self._make_api_response("QUESTION: Were tests run before or after the edit?")
        with patch("urllib.request.urlopen", return_value=question_resp):
            from utils import deepseek_verifier
            import importlib
            importlib.reload(deepseek_verifier)
            result1 = deepseek_verifier.verify_with_deepseek(
                {"tests": {"status": "done", "evidence": "pytest ok"}},
                state_file=state_file,
            )
        assert result1["pending"] is True

        # Simulate Claude answering via answer-deepseek.sh (append user answer to state)
        data = json.loads(state_file.read_text())
        data["messages"].append({"role": "user", "content": "I ran pytest AFTER the edit. Output: 9 passed in 1.2s."})
        state_file.write_text(json.dumps(data))

        # Second call: approval verdict
        approval = json.dumps({
            "approved": True,
            "verdict": "Tests confirmed genuine after clarification.",
            "suspicious_steps": [],
            "instructions": "",
        })
        verdict_resp = self._make_api_response(approval)
        with patch("urllib.request.urlopen", return_value=verdict_resp):
            importlib.reload(deepseek_verifier)
            result2 = deepseek_verifier.verify_with_deepseek(
                {"tests": {"status": "done", "evidence": "pytest ok"}},
                state_file=state_file,
            )
        assert result2["approved"] is True
        assert result2["pending"] is False

    def test_max_turns_forces_verdict(self, monkeypatch, tmp_path):
        """After 3+ questions in state, the next call forces JSON mode (verdict)."""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-key")

        # Pre-seed state with 3 question/answer turns already done
        state_file = tmp_path / "state.json"
        pre_state = {
            "messages": [
                {"role": "user", "content": "...initial evidence..."},
                {"role": "assistant", "content": "QUESTION: Q1?"},
                {"role": "user", "content": "A1"},
                {"role": "assistant", "content": "QUESTION: Q2?"},
                {"role": "user", "content": "A2"},
                {"role": "assistant", "content": "QUESTION: Q3?"},
                {"role": "user", "content": "A3"},
            ]
        }
        state_file.write_text(json.dumps(pre_state))

        payloads_sent = []

        verdict = json.dumps({
            "approved": False,
            "verdict": "Still insufficient after 3 clarifications.",
            "suspicious_steps": ["tests"],
            "instructions": "Run pytest and paste actual output.",
        })
        mock_resp = self._make_api_response(verdict)

        def capture_urlopen(req, timeout):
            import json as _json
            body = _json.loads(req.data.decode())
            payloads_sent.append(body)
            return mock_resp

        with patch("urllib.request.urlopen", side_effect=capture_urlopen):
            from utils import deepseek_verifier
            import importlib
            importlib.reload(deepseek_verifier)
            result = deepseek_verifier.verify_with_deepseek({}, state_file=state_file)

        # Should have forced JSON mode (response_format present)
        assert any("response_format" in p for p in payloads_sent)
        assert result["approved"] is False
        assert result["pending"] is False

    def test_verdict_clears_state_file(self, monkeypatch, tmp_path):
        """State file is deleted after a verdict is reached."""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-key")
        state_file = tmp_path / "state.json"
        # Pre-seed with one turn
        state_file.write_text(json.dumps({
            "messages": [{"role": "user", "content": "evidence"}]
        }))

        verdict = json.dumps({
            "approved": True, "verdict": "Looks good.", "suspicious_steps": [], "instructions": ""
        })
        mock_resp = self._make_api_response(verdict)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            from utils import deepseek_verifier
            import importlib
            importlib.reload(deepseek_verifier)
            result = deepseek_verifier.verify_with_deepseek({}, state_file=state_file)

        assert result["approved"] is True
        assert not state_file.exists()  # State file cleaned up

    def test_pending_result_has_all_keys(self, monkeypatch, tmp_path):
        """Pending result always has all expected keys."""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-key")
        mock_resp = self._make_api_response("QUESTION: Did you run tests?")
        with patch("urllib.request.urlopen", return_value=mock_resp):
            from utils import deepseek_verifier
            import importlib
            importlib.reload(deepseek_verifier)
            result = deepseek_verifier.verify_with_deepseek(
                {}, state_file=tmp_path / "state.json"
            )
        for key in ("approved", "verdict", "suspicious_steps", "instructions",
                    "skipped", "skip_reason", "pending", "questions"):
            assert key in result, f"Missing key: {key}"

    def test_skipped_result_has_pending_keys(self, monkeypatch):
        """Skipped result always includes pending and questions keys."""
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        from utils import deepseek_verifier
        import importlib
        importlib.reload(deepseek_verifier)
        result = deepseek_verifier.verify_with_deepseek({})
        assert "pending" in result
        assert "questions" in result
        assert result["pending"] is False
        assert result["questions"] == ""


# ─── Rejection continuation tests ────────────────────────────────────────────

class TestRejectionContinuation:
    """Tests for rejection-preservation behavior (negotiable-rejections plan)."""

    def _make_api_response(self, content: str) -> MagicMock:
        """Build a mock urllib response returning raw text content."""
        raw = json.dumps({
            "choices": [{"message": {"content": content}}]
        }).encode("utf-8")
        mock_resp = MagicMock()
        mock_resp.read.return_value = raw
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    def test_rejection_preserves_state_file(self, monkeypatch, tmp_path):
        """On rejection, state file is NOT deleted — conversation can continue."""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-key")
        state_file = tmp_path / "state.json"
        verdict = json.dumps({
            "approved": False,
            "verdict": "Evidence is insufficient.",
            "suspicious_steps": ["tests"],
            "instructions": "Run pytest and paste actual output.",
        })
        mock_resp = self._make_api_response(verdict)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            from utils import deepseek_verifier
            import importlib
            importlib.reload(deepseek_verifier)
            result = deepseek_verifier.verify_with_deepseek(
                {"tests": {"status": "done", "evidence": "ok"}},
                state_file=state_file,
            )
        assert result["approved"] is False
        assert result["pending"] is False
        assert state_file.exists(), "State file should survive rejection for conversation continuation"

    def test_rejection_state_has_verdict_in_history(self, monkeypatch, tmp_path):
        """After rejection, state file history contains the verdict as an assistant message."""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-key")
        state_file = tmp_path / "state.json"
        rejection_json = json.dumps({
            "approved": False,
            "verdict": "No real test execution found.",
            "suspicious_steps": ["tests"],
            "instructions": "Run pytest and paste actual output.",
        })
        mock_resp = self._make_api_response(rejection_json)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            from utils import deepseek_verifier
            import importlib
            importlib.reload(deepseek_verifier)
            deepseek_verifier.verify_with_deepseek(
                {"tests": {"status": "done", "evidence": "ok"}},
                state_file=state_file,
            )

        assert state_file.exists()
        data = json.loads(state_file.read_text())
        msgs = data.get("messages", [])
        asst_msgs = [m["content"] for m in msgs if m["role"] == "assistant"]
        assert any("approved" in m for m in asst_msgs), (
            "Rejection verdict JSON should appear in history as an assistant message"
        )

    def test_approved_deletes_state_file(self, monkeypatch, tmp_path):
        """Approval still deletes state file (existing behavior preserved)."""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-key")
        state_file = tmp_path / "state.json"
        state_file.write_text(json.dumps({
            "messages": [{"role": "user", "content": "evidence"}]
        }))

        verdict = json.dumps({
            "approved": True,
            "verdict": "Evidence is genuine.",
            "suspicious_steps": [],
            "instructions": "",
        })
        mock_resp = self._make_api_response(verdict)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            from utils import deepseek_verifier
            import importlib
            importlib.reload(deepseek_verifier)
            result = deepseek_verifier.verify_with_deepseek(
                {"tests": {"status": "done", "evidence": "47 passed"}},
                state_file=state_file,
            )

        assert result["approved"] is True
        assert not state_file.exists(), "State file should be cleared on approval"

    def test_conversation_continues_after_rejection(self, monkeypatch, tmp_path):
        """Pre-load state with rejection + user response, second call returns approval."""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-key")
        state_file = tmp_path / "state.json"

        # Simulate state after a rejection — verdict saved as assistant message,
        # user provided additional context via answer-deepseek.sh
        rejection_json = json.dumps({
            "approved": False,
            "verdict": "No test runner visible in bash history.",
            "suspicious_steps": ["tests"],
            "instructions": "Run pytest and paste actual output.",
        })
        pre_state = {
            "messages": [
                {"role": "user", "content": "...initial evidence..."},
                {"role": "assistant", "content": rejection_json},
                {"role": "user", "content": "I ran pytest in a separate terminal. Output: 9 passed in 1.2s."},
            ]
        }
        state_file.write_text(json.dumps(pre_state))

        # Second call: DeepSeek approves after seeing the additional context
        approval = json.dumps({
            "approved": True,
            "verdict": "Tests confirmed genuine after additional context.",
            "suspicious_steps": [],
            "instructions": "",
        })
        messages_sent = []

        def capture_urlopen(req, timeout):
            import json as _json
            body = _json.loads(req.data.decode())
            messages_sent.extend(body["messages"])
            return self._make_api_response(approval)

        with patch("urllib.request.urlopen", side_effect=capture_urlopen):
            from utils import deepseek_verifier
            import importlib
            importlib.reload(deepseek_verifier)
            result = deepseek_verifier.verify_with_deepseek({}, state_file=state_file)

        assert result["approved"] is True
        # Verify rejection + user response were included in the follow-up API call
        user_contents = [m["content"] for m in messages_sent if m["role"] == "user"]
        assert any("9 passed" in c for c in user_contents)

    def test_answer_deepseek_allows_after_rejection(self, tmp_path):
        """answer-deepseek.sh logic: when last message is a rejection JSON, appending still works."""
        state_file = tmp_path / "state.json"
        rejection_json = json.dumps({
            "approved": False,
            "verdict": "No test runner found.",
            "suspicious_steps": ["tests"],
            "instructions": "Run pytest.",
        })
        state = {
            "messages": [
                {"role": "user", "content": "...evidence..."},
                {"role": "assistant", "content": rejection_json},
            ]
        }
        state_file.write_text(json.dumps(state))

        # Simulate the logic from answer-deepseek.sh
        data = json.loads(state_file.read_text())
        msgs = data.get("messages", [])
        last_asst = next(
            (m["content"] for m in reversed(msgs) if m["role"] == "assistant"), ""
        )
        # New logic: allow responding if last_asst is non-empty (not just QUESTION:)
        assert last_asst, "Should find last assistant message"
        is_question = last_asst.strip().startswith("QUESTION:")
        assert not is_question, "Rejection verdict is not a question"

        # Append user response (simulating what answer-deepseek.sh does)
        msgs.append({"role": "user", "content": "I ran pytest separately. 9 passed."})
        data["messages"] = msgs
        state_file.write_text(json.dumps(data, indent=2))

        # Verify the state was updated correctly
        updated = json.loads(state_file.read_text())
        updated_msgs = updated.get("messages", [])
        last_user = next(
            (m["content"] for m in reversed(updated_msgs) if m["role"] == "user"), ""
        )
        assert "9 passed" in last_user
