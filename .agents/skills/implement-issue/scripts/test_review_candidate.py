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
from unittest import mock
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

    def evidence(self, name):
        return {'timed_out': False, 'returncode': 0, 'files_unchanged': True,
                'expected_files': {name: 'd' * 64},
                'receipt': {'completed': True, 'exit_code': 0, 'files_unchanged': True,
                            'candidate': {k: self.candidate[k] for k in ('head', 'content_sha256')},
                            'files': {name: 'd' * 64},
                            'tests': [{'test_id': 'New.test_new', 'file': name, 'sha256': 'd' * 64,
                                       'defined_here': True, 'started': 1, 'stopped': 1, 'successes': 1}]}}

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
        self.result['qa_execution_evidence'] = self.evidence('fresh.py')
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
                self.result['qa_execution_evidence'] = self.evidence('test_fresh.py')
                self.assertEqual(worker.validate_result(self.result, self.candidate, 'qa', self.required), [])

    def test_AC005_QA_receipt_requires_completed_new_case_and_exact_candidate_bytes(self):
        self.result['report']['role'] = 'qa'
        self.result['exploratory_files'] = ['fresh.py']
        self.result['report']['exploration'] = [{'command': 'python fresh.py', 'exit_code': 0}]
        self.result['events']['commands'].append({'command': 'python fresh.py', 'exit_code': 0, 'status': 'completed'})
        for change in ('missing', 'timeout', 'candidate', 'hash', 'empty', 'incomplete', 'changed', 'imported', 'started_only', 'failed', 'ambiguous'):
            with self.subTest(change=change):
                proof = self.evidence('fresh.py'); receipt = proof['receipt']
                if change == 'timeout': proof['timed_out'] = True
                if change == 'candidate': receipt['candidate']['head'] = 'e' * 40
                if change == 'hash': receipt['tests'][0]['sha256'] = 'e' * 64
                if change == 'empty': receipt['tests'] = []
                if change == 'incomplete': receipt['completed'] = False
                if change == 'changed': proof['files_unchanged'] = False
                if change == 'imported': receipt['tests'][0]['defined_here'] = False
                if change == 'started_only': receipt['tests'][0]['stopped'] = 0
                if change == 'failed': receipt['tests'][0]['successes'] = 0
                if change == 'ambiguous': receipt['tests'][0]['started'] = 2
                self.result['qa_execution_evidence'] = {} if change == 'missing' else proof
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
        (self.root / 'test_control.py').write_text('import unittest\nclass Existing(unittest.TestCase):\n def test_existing(self): self.assertEqual(1,1)\n')
        self.path = self.root / 'nested/test_new.py'
        self.path.write_text("import pathlib,unittest\nclass New(unittest.TestCase):\n def test_new(self): pathlib.Path('test-ran').write_text('yes')\nif __name__ == '__main__': unittest.main()\n")

    def result_for(self, command='python -m unittest nested.test_new -v', selected=None):
        fixture = ResultGates(); fixture.setUp()
        result = fixture.result; result['report']['role'] = 'qa'
        result['exploratory_files'] = ['nested/test_new.py']
        result['report']['exploratory_tests'] = selected if selected is not None else result['exploratory_files']
        run = subprocess.run(command, shell=True, cwd=self.root, capture_output=True, text=True)
        result['report']['exploration'] = [{'command': command, 'exit_code': run.returncode}]
        result['events']['commands'].append({'command': command, 'exit_code': run.returncode, 'status': 'completed' if run.returncode == 0 else 'failed'})
        return fixture, result, run

    def verify(self, expected=True, command='python -m unittest nested.test_new -v', timeout=5, selected=None):
        fixture, result, run = self.result_for(command, selected)
        result['qa_execution_evidence'] = worker.run_qa_tests(result, fixture.candidate, self.root, [], self.root / 'qa-0.unittest', timeout)
        result['problems'] = worker.validate_result(result, fixture.candidate, 'qa', fixture.required)
        self.assertEqual(not result['problems'], expected, (run.stderr, result['qa_execution_evidence'], result['problems']))
        return fixture, result

    def test_AC005_command_discovery_does_not_credit_an_undiscovered_case(self):
        fixture, result, run = self.result_for('python -m unittest discover -v')
        self.assertEqual(run.returncode, 0)
        self.assertIn('Ran 1 test', run.stderr)
        self.assertFalse((self.root / 'test-ran').exists())
        self.assertTrue(worker.validate_result(result, fixture.candidate, 'qa', fixture.required))

    def test_AC005_controlled_file_loading_executes_case_without_package_init(self):
        fixture, result = self.verify(command='python -m unittest discover -v')
        proof = result['qa_execution_evidence']
        self.assertTrue((self.root / 'test-ran').exists())
        self.assertTrue(proof['receipt']['tests'][0]['defined_here'])
        self.assertTrue(worker.qa_execution_ok(proof, fixture.candidate, result['exploratory_files']))
        self.assertEqual(worker.review_state({'qa': result}), 'clear')

    def test_AC005_direct_module_discovery_are_exploration_not_certification_rules(self):
        for command in ('python nested/test_new.py -v', 'python -m unittest nested.test_new -v',
                        'python -m unittest discover -s nested -v'):
            with self.subTest(command=command):
                self.verify(command=command)

    def test_AC005_async_receiver_name_does_not_change_execution_credit(self):
        self.path.write_text("import asyncio,pathlib,unittest\nclass New(unittest.IsolatedAsyncioTestCase):\n async def test_new(case):\n  await asyncio.sleep(0)\n  pathlib.Path('test-ran').write_text('yes')\n  case.assertEqual(7,7)\n")
        self.verify()

    def test_AC005_static_method_is_supported(self):
        self.path.write_text("import pathlib,unittest\nclass New(unittest.TestCase):\n @staticmethod\n def test_new(): pathlib.Path('test-ran').write_text('yes')\n")
        self.verify()

    def test_AC005_deferred_bodies_outside_standard_cycle_are_not_credited(self):
        for parent, method in (('TestCase', 'async def test_new(self): pass'),
                               ('TestCase', 'def test_new(self): yield 1'),
                               ('IsolatedAsyncioTestCase', 'async def test_new(self): yield 1')):
            with self.subTest(parent=parent, method=method):
                self.path.write_text('import unittest\nclass New(unittest.' + parent + '):\n ' + method + '\n')
                _, result = self.verify(False)
                self.assertEqual(result['qa_execution_evidence']['returncode'], 2)

    def test_AC005_imported_class_inherited_or_aliased_method_cannot_credit_new_case(self):
        for source in ('from test_control import Existing as New\n',
                       'from test_control import Existing\nclass New(Existing): pass\n',
                       'import unittest\nfrom test_control import Existing\nclass New(unittest.TestCase):\n test_new = Existing.test_existing\n'):
            with self.subTest(source=source):
                self.path.write_text(source)
                _, result = self.verify(False)
                self.assertFalse(any(t['defined_here'] for t in result['qa_execution_evidence']['receipt']['tests']))

    def test_AC005_failed_exploration_is_preserved_but_not_success_credit(self):
        self.path.write_text("import unittest\nclass New(unittest.TestCase):\n def test_new(self): self.fail('real defect')\n")
        _, result = self.verify(False)
        self.assertEqual(result['qa_execution_evidence']['returncode'], 1)
        self.assertIn('real defect', result['runner_findings'][0]['observed'])
        self.assertEqual(result['runner_findings'][0]['severity'], 'untriaged')
        self.assertEqual(worker.review_state({'qa': result}), 'incomplete')

    def test_AC005_success_does_not_hide_another_failed_case(self):
        self.path.write_text("import unittest\nclass New(unittest.TestCase):\n def test_good(self): self.assertEqual(1,1)\n def test_bad(self): self.fail('retain this defect')\n")
        _, result = self.verify()
        self.assertEqual(result['report']['verdict'], 'clear')  # Agent claim stays intact.
        self.assertEqual(worker.review_state({'qa': result}), 'findings')
        self.assertIn('retain this defect', result['runner_findings'][0]['observed'])

    def test_AC005_expected_failure_cannot_hide_behind_another_success(self):
        self.path.write_text("import unittest\nclass New(unittest.TestCase):\n def test_good(self): pass\n @unittest.expectedFailure\n def test_known(self): self.fail('expected but unresolved')\n")
        _, result = self.verify()
        self.assertEqual(worker.review_state({'qa': result}), 'findings')
        self.assertIn('expected but unresolved', str(result['runner_findings']))

    def test_AC005_multiple_cleanup_failures_keep_distinct_adjudication_ids(self):
        self.path.write_text("import unittest\nclass New(unittest.TestCase):\n def test_new(self):\n  self.addCleanup(self.fail, 'cleanup one')\n  self.addCleanup(self.fail, 'cleanup two')\n")
        _, result = self.verify(False)
        self.assertEqual(len(result['runner_findings']), 2)
        self.assertEqual(len({f['id'] for f in result['runner_findings']}), 2)

    def test_AC005_interruption_preserves_failures_already_collected(self):
        self.path.write_text("import unittest\nclass New(unittest.TestCase):\n def test_a_fail(self): self.fail('first defect survives interruption')\n def test_z_abort(self): raise KeyboardInterrupt('interrupted')\n")
        _, result = self.verify(False)
        self.assertFalse(result['qa_execution_evidence']['receipt']['completed'])
        self.assertIn('first defect survives interruption', str(result['runner_findings']))

    def test_AC005_skips_errors_and_special_outcomes_do_not_get_success_credit(self):
        sources = (
            "import unittest\nclass New(unittest.TestCase):\n @unittest.skip('no execution')\n def test_new(self): pass\n",
            "import unittest\nclass New(unittest.TestCase):\n def setUp(self): raise RuntimeError('prepare failed')\n def test_new(self): pass\n",
            "import unittest\nclass New(unittest.TestCase):\n @classmethod\n def setUpClass(cls): raise RuntimeError('class failed')\n def test_new(self): pass\n",
            "import unittest\ndef setUpModule(): raise RuntimeError('module failed')\nclass New(unittest.TestCase):\n def test_new(self): pass\n",
            "import unittest\nclass New(unittest.IsolatedAsyncioTestCase):\n async def asyncSetUp(self): self.skipTest('no body')\n async def test_new(self): pass\n",
            "import unittest\nclass New(unittest.TestCase):\n @unittest.expectedFailure\n def test_new(self): self.fail('expected')\n",
            "import unittest\nclass New(unittest.TestCase):\n @unittest.expectedFailure\n def test_new(self): pass\n",
            "import unittest\nclass New(unittest.TestCase):\n def test_new(self):\n  with self.subTest(x=1): self.fail('subtest failed')\n",
            "import unittest\nclass New(unittest.TestCase):\n def test_new(self):\n  with self.subTest(x=1): self.skipTest('subtest skipped')\n",
            "import unittest\nclass New(unittest.TestCase):\n def test_new(self): self.addCleanup(self.fail,'cleanup failed')\n",
            "import unittest\nclass New(unittest.TestCase):\n def tearDown(self): raise RuntimeError('teardown failed')\n def test_new(self): pass\n",
        )
        for source in sources:
            with self.subTest(source=source):
                self.path.write_text(source)
                self.verify(False)

    def test_AC005_empty_load_errors_and_custom_cycles_are_incomplete(self):
        for source in ("assert 1 == 1\n", "raise RuntimeError('import failed')\n",
                       "import unittest\nclass New(unittest.TestCase):\n def run(self,result=None): return result\n def test_new(self): pass\n",
                       "import unittest\ndef load_tests(loader,tests,pattern): return tests\nclass New(unittest.TestCase):\n def test_new(self): pass\n"):
            with self.subTest(source=source):
                self.path.write_text(source)
                _, result = self.verify(False, command='python -c "print(1)"')
                self.assertEqual(result['qa_execution_evidence']['returncode'], 2)

    def test_AC005_selected_files_must_be_explicit_new_regular_files(self):
        for selected in ([], ['test_control.py'], ['../escape.py'], ['nested/test_new.py'] * 2):
            with self.subTest(selected=selected):
                self.verify(False, selected=selected)
        self.path.unlink(); self.path.symlink_to(self.root / 'test_control.py')
        self.verify(False, selected=['nested/test_new.py'])

    def test_AC005_controlled_runner_timeout_and_source_changes_block(self):
        self.path.write_text("import time,unittest\nclass New(unittest.TestCase):\n def test_new(self): time.sleep(10)\n")
        _, result = self.verify(False, command='python -c "print(1)"', timeout=0.1)
        self.assertTrue(result['qa_execution_evidence']['timed_out'])
        self.path.write_text("import pathlib,unittest\nclass New(unittest.TestCase):\n def test_new(self): pathlib.Path(__file__).write_text('changed')\n")
        _, result = self.verify(False, command='python -c "print(1)"')
        self.assertFalse(result['qa_execution_evidence']['files_unchanged'])

    def test_AC005_controlled_runner_preserves_original_role_logs(self):
        original = {}
        for suffix in ('jsonl', 'stderr'):
            path = self.root / ('qa-0.' + suffix)
            path.write_text('original agent ' + suffix); original[path] = path.read_bytes()
        self.verify()
        self.assertTrue((self.root / 'qa-0.unittest.stderr').exists())
        for path, content in original.items():
            self.assertEqual(path.read_bytes(), content)

    def test_AC004_runner_findings_need_adjudication_before_incremental_review(self):
        fixture, result = self.verify()
        result['runner_findings'] = [{'id': 'QA-RUN-1'}]
        previous = {'candidate': fixture.candidate, 'roles': {'qa': result}}
        with self.assertRaises(ValueError):
            worker.incremental_context(previous, 'qa', fixture.candidate, [], self.root)
        decision = {'role': 'qa', 'finding': 'QA-RUN-1', 'candidate': fixture.candidate['content_sha256'],
                    'decision': 'rejected', 'evidence': 'independent contract repro'}
        with mock.patch.object(worker, 'git', return_value=b''):
            context = worker.incremental_context(previous, 'qa', fixture.candidate, [decision], self.root)
        self.assertEqual(context['own_previous_report']['runner_findings'], result['runner_findings'])


if __name__ == "__main__":
    unittest.main()
