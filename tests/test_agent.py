import contextlib
import io
import json
import os
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from repo_scout.agent import replay, run_agent
from repo_scout.gemini import GeminiClient, GeminiError, load_settings, output_text, validate
from repo_scout.policy import ANSWER_SCHEMA, choose_candidate, perspectives, score_candidate
from repo_scout.repo_tools import RepoTools


class ScriptedModel:
    """Test data only: no network access, no claims about real model quality."""
    model = "TEST_NOT_A_REAL_MODEL"

    def __init__(self, fail_at=None, invalid_final=False):
        self.records = []
        self.fail_at = fail_at
        self.invalid_final = invalid_final

    def redact(self, text):
        return text.replace("TEST_SECRET", "[REDACTED]")

    def ask(self, prompt, schema, label):
        record = {"label": label, "status": "started", "request": {"input": prompt}}
        self.records.append(record)
        if label == self.fail_at:
            record.update(status="error", error="TEST stopped")
            raise GeminiError("TEST stopped")
        if label.endswith("propose"):
            count = schema["properties"]["candidates"]["maxItems"]
            response = {"candidates": [{"plan": f"TEST plan {i}", "actions": [
                {"name": "read_file", "argument": "b.py" if i == 1 else "a.py", "start_line": 1}]}
                for i in range(count)]}
        elif label.endswith("evaluate"):
            ids = schema["properties"]["assessments"]["items"]["properties"]["id"]["enum"]
            response = {"assessments": [{"id": node, "hypothesis": "TEST hypothesis",
                "relevance": i % 3, "support": i % 3, "coverage": i % 3,
                "evidence": [{"path": "b.py" if i == 1 else "a.py", "line": 1}], "missing": "TEST unknown"}
                for i, node in enumerate(ids)]}
        else:
            response = {"answer": "TEST answer", "evidence": [{"path": "invented.py" if self.invalid_final else "a.py", "line": 1}],
                        "limitations": ["TEST only"]}
        validate(response, schema)
        record["status"] = "completed"
        return response


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "sample repo"
        self.root.mkdir()
        (self.root / "a.py").write_text("# alpha\nprint('hello')\n", encoding="utf-8")
        (self.root / "b.py").write_text("# beta\nresult = 1\n", encoding="utf-8")
        (self.root / ".env").write_text("GEMINI_API_KEY=TEST_SECRET", encoding="utf-8")
        (self.root / "secrets.json").write_text('{"key":"TEST_SECRET"}', encoding="utf-8")
        (self.root / "outputs").mkdir()
        (self.root / "outputs/old.py").write_text("TEST_SECRET", encoding="utf-8")

    def test_dotenv_handles_quotes_and_environment_precedence_without_exporting_other_values(self):
        env_file = Path(self.temp.name) / "config.env"
        env_file.write_text('export GEMINI_API_KEY="TEST_SECRET"\nGEMINI_MODEL=test-model # note\nUNRELATED=not-loaded\n', encoding="utf-8")
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(("TEST_SECRET", "test-model"), load_settings(env_file))
            self.assertNotIn("UNRELATED", os.environ)
        with patch.dict(os.environ, {"GEMINI_API_KEY": "override", "GEMINI_MODEL": "override-model"}):
            self.assertEqual(("override", "override-model"), load_settings(env_file))

    def test_tools_exclude_credentials_outputs_and_external_paths_and_freeze_source(self):
        tools = RepoTools(self.root)
        self.assertEqual({"a.py", "b.py"}, set(tools.files))
        self.assertFalse(tools.execute({"name": "search", "argument": "TEST_SECRET", "start_line": 1})["evidence"])
        self.assertFalse(tools.execute({"name": "read_file", "argument": "../.env", "start_line": 1})["evidence"])
        (self.root / "a.py").write_text("changed", encoding="utf-8")
        evidence = tools.execute({"name": "read_file", "argument": "a.py", "start_line": 2})["evidence"]
        self.assertEqual("print('hello')", evidence[0]["text"])
        with self.assertRaises(ValueError):
            RepoTools(self.root, [".env"])

    def test_unobserved_reference_cannot_win_despite_high_model_scores(self):
        observations = [{"evidence": [{"path": "a.py", "line": 1}]}]
        high = {"relevance": 2, "support": 2, "coverage": 2, "evidence": [{"path": "b.py", "line": 1}]}
        low = {"relevance": 1, "support": 1, "coverage": 1, "evidence": [{"path": "a.py", "line": 1}]}
        candidates = [{"id": "bad", "grading": score_candidate(high, observations)},
                      {"id": "good", "grading": score_candidate(low, observations)}]
        self.assertEqual("good", choose_candidate(candidates)["id"])
        self.assertEqual(1, len(perspectives("cot")))
        self.assertEqual(1, len(set(perspectives("tot"))))
        self.assertEqual(3, len(set(perspectives("diverse"))))

    def test_full_tree_uses_five_calls_and_only_selected_parent_memory(self):
        model = ScriptedModel()
        output = Path(self.temp.name) / "run"
        trace = run_agent(RepoTools(self.root), model, "TEST question", "diverse", 2, output)
        self.assertEqual("completed", trace["status"])
        self.assertEqual(5, len(model.records))
        self.assertEqual(["root", "d1-c3", "d2-c3"], trace["selected_path"])
        self.assertEqual(6, len(trace["nodes"]))
        second_proposal = model.records[2]["request"]["input"]
        self.assertNotIn('"path": "b.py"', second_proposal)
        self.assertIn('"id": "d1-c3"', second_proposal)
        self.assertNotIn("TEST_SECRET", (output / "snapshot.json").read_text(encoding="utf-8"))
        self.assertTrue((output / "report.md").is_file())
        with contextlib.redirect_stdout(io.StringIO()) as stream:
            replay(output)
        self.assertIn("d1-c3 → d2-c3", stream.getvalue())
        with self.assertRaises(ValueError):
            run_agent(RepoTools(self.root), model, "TEST", "diverse", 2, output)

    def test_failure_retains_partial_tree_without_claiming_success(self):
        output = Path(self.temp.name) / "partial"
        with self.assertRaises(GeminiError):
            run_agent(RepoTools(self.root), ScriptedModel(fail_at="level-2-evaluate"), "TEST", "tot", 2, output)
        trace = json.loads((output / "trace.json").read_text(encoding="utf-8"))
        self.assertEqual("failed", trace["status"])
        self.assertEqual(6, len(trace["nodes"]))
        self.assertNotIn("answer", trace)
        calls = json.loads((output / "calls.json").read_text(encoding="utf-8"))
        self.assertEqual("error", calls[-1]["status"])
        self.assertEqual(3, sum(call["status"] == "completed" for call in calls))

    def test_final_answer_with_unobserved_reference_is_rejected(self):
        with self.assertRaisesRegex(GeminiError, "관찰하지 않은"):
            run_agent(RepoTools(self.root), ScriptedModel(invalid_final=True), "TEST", "cot", 1,
                      Path(self.temp.name) / "invalid")

    def test_adapter_reads_public_output_and_enforces_budget_without_logging_key(self):
        response = {"status": "completed", "usage": {"total_tokens": 10}, "steps": [
            {"type": "thought", "content": [{"type": "text", "text": "not a public output"}]},
            {"type": "model_output", "content": [{"type": "text", "text": '{"ok": true}'}]}]}
        schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]}
        model = GeminiClient("TEST_SECRET", "test-model", max_calls=1, interval=0)
        with patch("repo_scout.gemini.urlopen", return_value=io.BytesIO(json.dumps(response).encode())):
            self.assertTrue(model.ask("test TEST_SECRET", schema, "TEST")["ok"])
        self.assertNotIn("TEST_SECRET", json.dumps(model.records))
        self.assertEqual('{"ok": true}', output_text(response))
        with self.assertRaisesRegex(GeminiError, "최대"):
            model.ask("test", schema, "TEST")

    def test_dns_error_and_http_auth_error_are_distinguished_and_redacted(self):
        schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]}
        model = GeminiClient("TEST_SECRET", interval=0)
        with patch("repo_scout.gemini.urlopen", side_effect=URLError(socket.gaierror(11001, "host not found"))):
            with self.assertRaisesRegex(GeminiError, "DNS"):
                model.ask("test", schema, "TEST")
        self.assertEqual("dns", model.records[0]["phase"])
        error = HTTPError("https://example.invalid", 403, "forbidden", {}, io.BytesIO(b"TEST_SECRET rejected"))
        with patch("repo_scout.gemini.urlopen", side_effect=error):
            with self.assertRaisesRegex(GeminiError, "HTTP 403") as caught:
                model.ask("test", schema, "TEST")
        self.assertNotIn("TEST_SECRET", str(caught.exception))
        self.assertNotIn("TEST_SECRET", json.dumps(model.records))

    def test_schema_rejects_boolean_where_integer_is_required(self):
        with self.assertRaises(GeminiError):
            validate(True, {"type": "integer"})
        with self.assertRaises(GeminiError):
            validate({"answer": "TEST", "evidence": [], "limitations": ["TEST"]}, ANSWER_SCHEMA)


if __name__ == "__main__":
    unittest.main()
