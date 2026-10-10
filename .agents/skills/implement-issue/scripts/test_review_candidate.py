"""https://github.com/lvckss/piia2-26/issues/26#issuecomment-6097049466 AC-001–008.

Deterministic gates complement, and do not replace, the live Codex evaluation.
"""
import copy
import os
import pathlib
import subprocess
import signal
import sys
import tempfile
import time
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

    def observation(self, command, name):
        return {'command': command, 'timed_out': False, 'returncode': 0,
                'expected_files': {name: 'd' * 64},
                'observation': {'completed': True, 'exit_code': 0, 'files_unchanged': True,
                                'tests': [{'test_id': 'New.test_new', 'file': name, 'sha256': 'd' * 64}]}}

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

    def test_AC003_QA_cannot_relabel_required_check_as_exploration(self):
        self.result['report']['role'] = 'qa'
        self.result['report']['exploration'] = self.result['report']['checks'].copy()
        self.result['exploratory_files'] = ['fresh.py']
        self.assertTrue(worker.validate_result(self.result, self.candidate, 'qa', self.required))

    def test_AC005_resume_incomplete_role_with_full_coverage_and_preserved_budget(self):
        previous = {'technical_retries': {'reviewer': 0}, 'roles': {'reviewer': {'problems': ['preflight failure']}}}
        context, retries = worker.next_review_context(previous, 'reviewer', {}, [], pathlib.Path('.'))
        self.assertEqual(context, {})
        self.assertEqual(retries, 1)
        previous['technical_retries']['reviewer'] = 1
        with self.assertRaises(ValueError):
            worker.next_review_context(previous, 'reviewer', {}, [], pathlib.Path('.'))

    def test_AC003_QA_new_test_must_be_executed(self):
        self.result['report']['role'] = 'qa'
        self.result['exploratory_files'] = ['fresh.py']
        self.result['report']['exploration'] = [{'command': 'python fresh.py', 'exit_code': 0}]
        self.result['events']['commands'].append({'command': 'python fresh.py', 'exit_code': 0, 'status': 'completed'})
        self.result['qa_execution_evidence'] = [self.observation('python fresh.py', 'fresh.py')]
        self.assertEqual(worker.validate_result(self.result, self.candidate, 'qa', self.required), [])
        self.result['exploratory_files'] = ['unused.py']
        self.assertTrue(worker.validate_result(self.result, self.candidate, 'qa', self.required))

    def test_AC003_QA_file_mention_is_not_execution(self):
        self.result['report']['role'] = 'qa'
        self.result['exploratory_files'] = ['fresh.py']
        for command in ('cat fresh.py', 'echo fresh.py', 'python -c "print(1)" fresh.py'):
            with self.subTest(command=command):
                self.result['report']['exploration'] = [{'command': command, 'exit_code': 0}]
                self.result['events']['commands'].append({'command': command, 'exit_code': 0, 'status': 'completed'})
                self.assertTrue(worker.validate_result(self.result, self.candidate, 'qa', self.required))

    def test_AC003_QA_unittest_module_and_discovery_execute_new_test(self):
        self.result['report']['role'] = 'qa'
        self.result['exploratory_files'] = ['test_fresh.py']
        for command in ('python -m unittest test_fresh -v',
                        'python -m unittest discover -p test_fresh.py -v'):
            with self.subTest(command=command):
                self.result['report']['exploration'] = [{'command': command, 'exit_code': 0}]
                self.result['events']['commands'].append({'command': command, 'exit_code': 0, 'status': 'completed'})
                self.result['qa_execution_evidence'] = [self.observation(command, 'test_fresh.py')]
                self.assertEqual(worker.validate_result(self.result, self.candidate, 'qa', self.required), [])

    def test_AC005_QA_observation_must_be_complete_and_bound_to_command_and_bytes(self):
        self.result['report']['role'] = 'qa'
        self.result['exploratory_files'] = ['fresh.py']
        self.result['report']['exploration'] = [{'command': 'python fresh.py', 'exit_code': 0}]
        self.result['events']['commands'].append({'command': 'python fresh.py', 'exit_code': 0, 'status': 'completed'})
        for change in ('missing', 'timeout', 'command', 'hash', 'empty', 'incomplete', 'changed'):
            with self.subTest(change=change):
                proof = self.observation('python fresh.py', 'fresh.py')
                if change == 'timeout': proof['timed_out'] = True
                if change == 'command': proof['command'] = 'python another.py'
                if change == 'hash': proof['observation']['tests'][0]['sha256'] = 'e' * 64
                if change == 'empty': proof['observation']['tests'] = []
                if change == 'incomplete': proof['observation']['completed'] = False
                if change == 'changed': proof['observation']['files_unchanged'] = False
                self.result['qa_execution_evidence'] = [] if change == 'missing' else [proof]
                self.assertTrue(worker.validate_result(self.result, self.candidate, 'qa', self.required))

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

    def test_AC005_timeout_kills_sigterm_resistant_descendant(self):
        child = "import signal,time,pathlib; signal.signal(signal.SIGTERM,signal.SIG_IGN); pathlib.Path('ready').write_text('ready'); time.sleep(1); pathlib.Path('survived').write_text('alive'); time.sleep(20)"
        parent = "import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',sys.argv[1]]); time.sleep(20)"
        result = worker.run_process([sys.executable, '-c', parent, child], self.root, '', self.root / 'attempt', 0.5)
        try:
            self.assertTrue(result['timed_out'])
            self.assertTrue((self.root / 'ready').exists())
            time.sleep(1)
            self.assertFalse((self.root / 'survived').exists())
        finally:
            try: os.killpg(result['pid'], signal.SIGKILL)
            except ProcessLookupError: pass


class QAExecutionEvidence(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        (self.root / 'nested').mkdir()
        (self.root / 'test_control.py').write_text('import unittest\nclass Control(unittest.TestCase):\n def test_existing(self): self.assertEqual(1,1)\n')
        (self.root / 'nested/test_new.py').write_text("import pathlib,unittest\nclass New(unittest.TestCase):\n def test_new(self): pathlib.Path('test-ran').write_text('yes')\nif __name__ == '__main__': unittest.main()\n")

    def result_for(self, command):
        fixture = ResultGates(); fixture.setUp()
        result = fixture.result; result['report']['role'] = 'qa'
        result['exploratory_files'] = ['nested/test_new.py']
        run = subprocess.run(command, shell=True, cwd=self.root, capture_output=True, text=True)
        result['report']['exploration'] = [{'command': command, 'exit_code': run.returncode}]
        result['events']['commands'].append({'command': command, 'exit_code': run.returncode, 'status': 'completed' if run.returncode == 0 else 'failed'})
        return fixture, result, run

    def test_AC005_discovery_skipping_new_test_blocks_even_when_existing_tests_pass(self):
        fixture, result, run = self.result_for('python -m unittest discover -v')
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn('Ran 1 test', run.stderr)
        self.assertFalse((self.root / 'test-ran').exists())
        self.assertTrue(worker.validate_result(result, fixture.candidate, 'qa', fixture.required),
                        'exit 0 and matching nested filename wrongly credit a test unittest skipped')

    def verify(self, command, expected=True):
        fixture, result, run = self.result_for(command)
        result['qa_execution_evidence'] = worker.prove_qa_execution(result, self.root, [], self.root / 'observation', 5)
        problems = worker.validate_result(result, fixture.candidate, 'qa', fixture.required)
        self.assertEqual(not problems, expected, (run.stderr, result['qa_execution_evidence'], problems))
        return result['qa_execution_evidence']

    def test_AC005_positive_direct_module_and_explicit_nonpackage_discovery(self):
        for command in ('python nested/test_new.py -v',
                        'python -m unittest nested.test_new -v',
                        'python -m unittest discover -s nested -v'):
            with self.subTest(command=command):
                proof = self.verify(command)
                self.assertTrue((self.root / 'test-ran').exists())
                self.assertEqual(proof[0]['observation']['tests'][0]['file'], 'nested/test_new.py')

    def test_AC005_discovery_traverses_package_and_observes_new_method(self):
        (self.root / 'nested/__init__.py').write_text('')
        self.verify('python -m unittest discover -v')
        self.assertTrue((self.root / 'test-ran').exists())

    def test_AC005_observed_discovery_skipping_nonpackage_is_rejected(self):
        proof = self.verify('python -m unittest discover -v', False)
        self.assertEqual(proof[0]['observation']['tests'], [])
        self.assertFalse((self.root / 'test-ran').exists())

    def test_AC005_module_running_only_existing_test_has_no_new_credit(self):
        self.verify('python -m unittest test_control -v', False)

    def test_AC005_import_only_and_direct_without_unittest_run_have_no_credit(self):
        (self.root / 'import_only.py').write_text('import nested.test_new\n')
        self.verify('python import_only.py', False)
        p = self.root / 'nested/test_new.py'
        p.write_text(p.read_text().split("if __name__")[0])
        self.verify('python nested/test_new.py', False)

    def test_AC005_skipped_unittest_has_no_method_execution_credit(self):
        p = self.root / 'nested/test_new.py'
        p.write_text(p.read_text().replace(' def test_new', " @unittest.skip('not executed')\n def test_new"))
        self.verify('python -m unittest nested.test_new -v', False)

    def test_AC005_failing_new_method_is_observed_as_defect_evidence(self):
        p = self.root / 'nested/test_new.py'
        p.write_text(p.read_text().replace("pathlib.Path('test-ran').write_text('yes')", 'self.fail("real defect")'))
        proof = self.verify('python nested/test_new.py -v')
        self.assertEqual(proof[0]['observation']['exit_code'], 1)
        self.assertTrue(proof[0]['observation']['tests'])

    def test_AC005_production_observation_prefix_preserves_original_role_logs(self):
        fixture, result, run = self.result_for('python nested/test_new.py -v')
        self.assertEqual(run.returncode, 0)
        original = {}
        for suffix in ('jsonl', 'stderr'):
            path = self.root / ('qa-0.' + suffix)
            path.write_text('original model ' + suffix)
            original[path] = path.read_bytes()
        result['qa_execution_evidence'] = worker.prove_qa_execution(result, self.root, [], self.root / 'qa-0.observation', 5)
        self.assertEqual(worker.validate_result(result, fixture.candidate, 'qa', fixture.required), [])
        self.assertTrue((self.root / 'qa-0.observation-0.stderr').exists())
        for path, content in original.items(): self.assertEqual(path.read_bytes(), content)

    def test_AC005_async_method_is_actually_executed_and_credited(self):
        p = self.root / 'nested/test_new.py'
        p.write_text("import asyncio,pathlib,unittest\nclass New(unittest.IsolatedAsyncioTestCase):\n async def test_new(self):\n  await asyncio.sleep(0)\n  pathlib.Path('test-ran').write_text('yes')\nif __name__ == '__main__': unittest.main()\n")
        for command in ('python nested/test_new.py -v', 'python -m unittest nested.test_new -v', 'python -m unittest discover -s nested -v'):
            with self.subTest(command=command):
                self.verify(command)
                self.assertTrue((self.root / 'test-ran').exists())

    def test_AC005_async_setup_skip_has_no_body_credit(self):
        p = self.root / 'nested/test_new.py'
        p.write_text("import pathlib,unittest\nclass New(unittest.IsolatedAsyncioTestCase):\n async def asyncSetUp(self): self.skipTest('no method body')\n async def test_new(self): pathlib.Path('test-ran').write_text('yes')\n")
        self.verify('python -m unittest nested.test_new -v', False)
        self.assertFalse((self.root / 'test-ran').exists())

    def test_AC005_async_called_outside_unittest_run_has_no_framework_credit(self):
        p = self.root / 'nested/test_new.py'
        p.write_text("import asyncio,pathlib,unittest\nclass New(unittest.IsolatedAsyncioTestCase):\n async def test_new(self): pathlib.Path('test-ran').write_text('yes')\nif __name__ == '__main__': asyncio.run(New().test_new())\n")
        self.verify('python nested/test_new.py', False)
        self.assertTrue((self.root / 'test-ran').exists())

    def test_AC005_sync_static_test_keeps_execution_credit(self):
        p = self.root / 'nested/test_new.py'
        p.write_text("import pathlib,unittest\nclass New(unittest.TestCase):\n @staticmethod\n def test_new(): pathlib.Path('test-ran').write_text('yes')\n")
        self.verify('python -m unittest nested.test_new -v')


if __name__ == "__main__":
    unittest.main()
