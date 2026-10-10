#!/usr/bin/env python3
"""Private controlled runner: standard unittest only, no execution tracing."""
from collections import Counter
from contextlib import redirect_stdout
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import sys
import traceback
import unittest


class Result(unittest.TestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.started = Counter(); self.stopped = Counter(); self.successes = Counter()

    def startTest(self, test):
        self.started[test.id()] += 1
        super().startTest(test)

    def stopTest(self, test):
        self.stopped[test.id()] += 1
        super().stopTest(test)

    def addSuccess(self, test):
        self.successes[test.id()] += 1
        super().addSuccess(test)


def cases(suite):
    for test in suite:
        if type(test) is unittest.TestSuite:
            yield from cases(test)
        elif isinstance(test, unittest.TestCase) and not isinstance(test, unittest.FunctionTestCase):
            yield test
        else:
            raise ValueError('Only standard TestSuite/TestCase execution is supported.')


def source_file(obj):
    filename = inspect.getsourcefile(obj)
    return Path(filename).resolve() if filename else None


def run(request):
    root = Path.cwd(); expected = request['files']
    receipt = {'candidate': request['candidate'], 'files': expected, 'completed': False,
               'files_unchanged': False, 'tests': [], 'issues': [], 'exit_code': 2}
    result = Result(); records = []
    def unchanged():
        return all(not (root / name).is_symlink() and (root / name).resolve().is_relative_to(root) and
                   hashlib.sha256((root / name).read_bytes()).hexdigest() == sha for name, sha in expected.items())
    try:
        if not expected or not unchanged():
            raise ValueError('Missing or changed exploratory source.')
        sys.path.insert(0, str(root)); os.environ['TMPDIR'] = str(root)
        suite = unittest.TestSuite()
        with redirect_stdout(sys.stderr):
            for name, sha in expected.items():
                path = (root / name).resolve()
                module_name = 'qa_' + hashlib.sha256(name.encode()).hexdigest()[:12]
                spec = importlib.util.spec_from_file_location(module_name, path)
                module = importlib.util.module_from_spec(spec); sys.modules[module_name] = module
                spec.loader.exec_module(module)
                if hasattr(module, 'load_tests'):
                    raise ValueError('Custom load_tests hooks are not supported.')
                loader = unittest.TestLoader(); loaded = list(cases(loader.loadTestsFromModule(module)))
                if loader.errors:
                    raise ValueError('\n'.join(loader.errors))
                for test in loaded:
                    cls = type(test)
                    standard_run = unittest.IsolatedAsyncioTestCase.run if isinstance(test, unittest.IsolatedAsyncioTestCase) else unittest.TestCase.run
                    if cls.run is not standard_run or cls.__call__ is not unittest.TestCase.__call__ or cls.id is not unittest.TestCase.id:
                        raise ValueError('Custom run/__call__/id cycles are not supported.')
                    method = getattr(cls, test.id().rsplit('.', 1)[-1])
                    if inspect.isgeneratorfunction(method) or inspect.isasyncgenfunction(method) or (
                            inspect.iscoroutinefunction(method) and not isinstance(test, unittest.IsolatedAsyncioTestCase)):
                        raise ValueError('Deferred test bodies outside the standard unittest cycle are not supported.')
                    records.append({'test_id': test.id(), 'file': name, 'sha256': sha,
                                    'defined_here': source_file(cls) == path and source_file(method) == path})
                suite.addTests(loaded)
            if not records or len({r['test_id'] for r in records}) != len(records):
                raise ValueError('Empty suite or ambiguous duplicate test identities.')
            result.startTestRun()
            try:
                suite.run(result)
            finally:
                result.stopTestRun()
        receipt['completed'] = True
    except BaseException:
        receipt['issues'].append({'test_id': 'controlled-runner', 'kind': 'error', 'detail': traceback.format_exc()})
    # Keep public result collections even when the suite was interrupted.
    for record in records:
        identity = record['test_id']
        receipt['tests'].append({**record, 'started': result.started[identity],
                                 'stopped': result.stopped[identity], 'successes': result.successes[identity]})
    for kind, entries in (('failure', result.failures), ('error', result.errors),
                          ('skip', result.skipped), ('expected_failure', result.expectedFailures)):
        receipt['issues'].extend({'test_id': test.id(), 'kind': kind, 'detail': detail} for test, detail in entries)
    receipt['issues'].extend({'test_id': test.id(), 'kind': 'unexpected_success',
                              'detail': 'Unexpected success of an expected-failure case.'} for test in result.unexpectedSuccesses)
    receipt['completed'] = receipt['completed'] and all(r['started'] == r['stopped'] == 1 for r in receipt['tests'])
    receipt['exit_code'] = 0 if result.wasSuccessful() else 1
    try:
        receipt['files_unchanged'] = unchanged()
    except OSError:
        pass
    if not receipt['completed'] or not receipt['files_unchanged']:
        receipt['exit_code'] = 2
    return receipt


if __name__ == '__main__':
    receipt = run(json.loads(sys.stdin.read()))
    print(json.dumps(receipt))
    sys.exit(receipt['exit_code'])
