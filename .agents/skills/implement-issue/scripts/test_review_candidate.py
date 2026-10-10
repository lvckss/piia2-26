"""https://github.com/lvckss/piia2-26/issues/26#issuecomment-6097049466 AC-001–008.

Deterministic gates complement, and do not replace, the live Codex evaluation.
"""
import copy
import pathlib
import subprocess
import tempfile
import unittest
import review_candidate as worker


class ResultGates(unittest.TestCase):
    def setUp(self):
        self.candidate = {"head": "a" * 40, "content_sha256": "b" * 64, "files": {"code.py": "c" * 64}}
        self.required = ["python -m unittest -v"]
        self.result = {"returncode": 0, "timed_out": False, "source_unchanged": True,
                       "probe_ok": True, "events": {"completed": True, "errors": [], "thread_ids": ["one"],
                       "commands": [{"command": "python -m unittest -v", "exit_code": 0, "status": "completed"}]},
                       "report": {"role": "reviewer", "candidate": self.candidate, "status": "complete",
                                  "verdict": "clear", "checks": [{"command": self.required[0], "exit_code": 0}],
                                  "findings": [], "exploration": []}}

    def test_AC005_rejects_exit_zero_with_incomplete_report(self):
        self.result["report"]["status"] = "incomplete"
        self.assertTrue(worker.validate_result(self.result, self.candidate, "reviewer", self.required))

    def test_AC005_missing_report_and_timeout_are_not_success(self):
        for key, value in [("report", None), ("timed_out", True), ("returncode", 1)]:
            with self.subTest(key=key):
                result = copy.deepcopy(self.result); result[key] = value
                self.assertTrue(worker.validate_result(result, self.candidate, "reviewer", self.required))

    def test_AC001_AC004_stale_candidate_is_rejected(self):
        self.result["report"]["candidate"]["head"] = "d" * 40
        expected = {**self.candidate, "head": "a" * 40}
        self.assertTrue(worker.validate_result(self.result, expected, "reviewer", self.required))

    def test_AC002_permission_failure_or_source_change_blocks(self):
        for key in ("probe_ok", "source_unchanged"):
            result = copy.deepcopy(self.result); result[key] = False
            self.assertTrue(worker.validate_result(result, self.candidate, "reviewer", self.required))

    def test_AC005_claimed_check_must_have_successful_actual_execution(self):
        for commands in ([], [{"command": self.required[0], "exit_code": 1, "status": "completed"}],
                         [{"command": "printf 'python -m unittest -v'", "exit_code": 0, "status": "completed"}]):
            result = copy.deepcopy(self.result); result["events"]["commands"] = commands
            self.assertTrue(worker.validate_result(result, self.candidate, "reviewer", self.required))

    def test_AC005_valid_review_is_complete(self):
        self.assertEqual(worker.validate_result(self.result, self.candidate, "reviewer", self.required), [])

    def test_AC003_exploratory_failure_is_executed_defect_evidence(self):
        self.result['events']['commands'].append({'command': 'python repro.py', 'exit_code': 1, 'status': 'failed'})
        self.result['report']['exploration'] = [{'command': 'python repro.py', 'exit_code': 1}]
        self.assertEqual(worker.validate_result(self.result, self.candidate, 'reviewer', self.required), [])

    def test_AC005_export_then_actual_check_is_recognized(self):
        self.result['events']['commands'][0]['command'] = "/usr/bin/zsh -lc 'export PYTHONDONTWRITEBYTECODE=1\npython -m unittest -v'"
        self.assertEqual(worker.validate_result(self.result, self.candidate, 'reviewer', self.required), [])

    def test_AC005_export_without_execution_is_not_a_check(self):
        self.assertNotEqual(worker.normalize_command('export FOO=1 python'), ['python'])

    def test_AC005_malformed_reports_are_rejected(self):
        for report in ([], 'success', {'role': 'reviewer', 'candidate': []}, {'findings': 'none'}):
            result = copy.deepcopy(self.result); result['report'] = report
            self.assertTrue(worker.validate_result(result, self.candidate, 'reviewer', self.required))

    def test_AC007_agent_claimed_usage_is_ignored(self):
        event = {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': 'usage: 999 input tokens'}}
        self.assertIsNone(worker.summarize_events([event])['usage']['input_tokens'])

    def test_AC006_correction_budget_is_preserved_and_exhaustion_blocks(self):
        previous = {'correction_batches': 2, 'candidate': {'content_sha256': 'old'}}
        self.assertEqual(worker.correction_batches(previous, {'content_sha256': 'old'}), 2)
        with self.assertRaises(ValueError):
            worker.correction_batches(previous, {'content_sha256': 'new'})
        self.assertEqual(worker.correction_batches(None, {'content_sha256': 'new'}), 0)

    def test_AC003_QA_requires_actual_exploration(self):
        self.result["report"]["role"] = "qa"
        self.assertTrue(worker.validate_result(self.result, self.candidate, "qa", self.required))

    def test_AC007_absent_usage_is_unknown(self):
        usage = worker.summarize_events([])["usage"]
        self.assertEqual(usage, {"input_tokens": None, "output_tokens": None, "cached_input_tokens": None})

    def test_AC007_usage_comes_only_from_runtime(self):
        usage = {"input_tokens": 123, "output_tokens": 17, "cached_input_tokens": 90}
        self.assertEqual(worker.summarize_events([{"type": "turn.completed", "usage": usage}])["usage"], usage)

    def test_AC005_failed_turn_and_error_are_retained(self):
        result = worker.summarize_events([{"type": "turn.failed", "error": "permission error"}])
        self.assertFalse(result["completed"])
        self.assertTrue(result["errors"])


class CandidateIsolation(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.repo = self.root / 'repo'; self.repo.mkdir()
        self.git('init', '-q')
        (self.repo / 'source.py').write_text('print(1)\n')
        self.git('add', 'source.py')
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'base')

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args]).decode().strip()

    def test_AC001_snapshot_matches_git_and_ignores_uncommitted_changes(self):
        candidate = worker.freeze(self.repo, ['source.py'], self.root / 'snapshot')
        self.assertEqual(candidate['head'], self.git('rev-parse', 'HEAD'))
        self.assertEqual(candidate['content_sha256'], worker.fingerprint(candidate['files']))
        (self.repo / 'source.py').write_text('print(2)\n')
        self.assertEqual((self.root / 'snapshot/source.py').read_text(), 'print(1)\n')
        with self.assertRaises(ValueError):
            worker.freeze(self.repo, ['source.py'], self.root / 'dirty')

    def test_AC002_rejects_path_traversal_and_symlinks(self):
        for name in ('../source.py', '/etc/passwd'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                worker.freeze(self.repo, [name], self.root / ('bad' + str(len(name))))
        (self.repo / 'link').symlink_to('/etc/passwd')
        self.git('add', 'link'); self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'link')
        with self.assertRaises(ValueError):
            worker.freeze(self.repo, ['link'], self.root / 'linked')

    def test_AC004_incremental_requires_evidence_and_only_own_report(self):
        previous = {'candidate': {'head': self.git('rev-parse', 'HEAD'), 'content_sha256': 'old'},
                    'roles': {'reviewer': {'problems': [], 'report': {'findings': [{'id': 'R1'}]}},
                              'qa': {'report': {'secret_peer_verdict': 'do not copy'}}}}
        candidate = {'head': previous['candidate']['head'], 'files': {'source.py': 'hash'}}
        with self.assertRaises(ValueError):
            worker.incremental_context(previous, 'reviewer', candidate, [], self.repo)
        decisions = [{'role': 'reviewer', 'candidate': 'old', 'finding': 'R1', 'decision': 'rejected', 'evidence': 'executed contract repro'}]
        context = worker.incremental_context(previous, 'reviewer', candidate, decisions, self.repo)
        self.assertNotIn('secret_peer_verdict', str(context))
        self.assertEqual(context['own_decisions'], decisions)
        previous['roles']['reviewer']['problems'] = ['timeout']
        with self.assertRaises(ValueError):
            worker.incremental_context(previous, 'reviewer', candidate, decisions, self.repo)


if __name__ == "__main__":
    unittest.main()
