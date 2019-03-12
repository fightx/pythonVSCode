# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import os
import os.path
import unittest

from ...util import Stub, StubProxy
from testing_tools.adapter.errors import UnsupportedCommandError
from testing_tools.adapter.info import TestInfo, TestPath, ParentInfo
from testing_tools.adapter.pytest import (
        discover, add_cli_subparser, TestCollector, DiscoveredTests
        )


class StubSubparsers(StubProxy):

    def __init__(self, stub=None, name='subparsers'):
        super(StubSubparsers, self).__init__(stub, name)

    def add_parser(self, name):
        self.add_call('add_parser', None, {'name': name})
        return self.return_add_parser


class StubArgParser(StubProxy):

    def __init__(self, stub=None):
        super(StubArgParser, self).__init__(stub, 'argparser')

    def add_argument(self, *args, **kwargs):
        self.add_call('add_argument', args, kwargs)


class StubPyTest(StubProxy):

    def __init__(self, stub=None):
        super(StubPyTest, self).__init__(stub, 'pytest')
        self.return_main = 0

    def main(self, args, plugins):
        self.add_call('main', None, {'args': args, 'plugins': plugins})
        return self.return_main


class StubPlugin(StubProxy):

    _started = True

    def __init__(self, stub=None, tests=None):
        super(StubPlugin, self).__init__(stub, 'plugin')
        if tests is None:
            tests = StubDiscoveredTests(self.stub)
        self._tests = tests

    def __getattr__(self, name):
        if not name.startswith('pytest_'):
            raise AttributeError(name)
        def func(*args, **kwargs):
            self.add_call(name, args or None, kwargs or None)
        return func


class StubDiscoveredTests(StubProxy):

    NOT_FOUND = object()

    def __init__(self, stub=None):
        super().__init__(stub, 'discovered')
        self.return_items = []
        self.return_parents = []

    def __len__(self):
        self.add_call('__len__', None, None)
        return len(self.return_items)

    def __getitem__(self, index):
        self.add_call('__getitem__', (index,), None)
        return self.return_items[index]

    @property
    def parents(self):
        self.add_call('parents', None, None)
        return self.return_parents

    def reset(self):
        self.add_call('reset', None, None)

    def add_test(self, test, suiteids):
        self.add_call('add_test', None, {'test': test, 'suiteids': suiteids})


class FakeFunc(object):

    def __init__(self, name):
        self.__name__ = name


class FakeMarker(object):

    def __init__(self, name):
        self.name = name


class StubPytestItem(StubProxy):

    def __init__(self, stub=None, **attrs):
        super(StubPytestItem, self).__init__(stub, 'pytest.Item')
        self.__dict__.update(attrs)
        if 'own_markers' not in attrs:
            self.own_markers = ()

    def __getattr__(self, name):
        self.add_call(name + ' (attr)', None, None)
        def func(*args, **kwargs):
            self.add_call(name, args or None, kwargs or None)
        return func


class StubPytestSession(StubProxy):

    def __init__(self, stub=None):
        super(StubPytestSession, self).__init__(stub, 'pytest.Session')

    def __getattr__(self, name):
        self.add_call(name + ' (attr)', None, None)
        def func(*args, **kwargs):
            self.add_call(name, args or None, kwargs or None)
        return func


class StubPytestConfig(StubProxy):

    def __init__(self, stub=None):
        super(StubPytestConfig, self).__init__(stub, 'pytest.Config')

    def __getattr__(self, name):
        self.add_call(name + ' (attr)', None, None)
        def func(*args, **kwargs):
            self.add_call(name, args or None, kwargs or None)
        return func


##################################
# tests

class AddCLISubparserTests(unittest.TestCase):

    def test_discover(self):
        stub = Stub()
        subparsers = StubSubparsers(stub)
        parser = StubArgParser(stub)
        subparsers.return_add_parser = parser

        add_cli_subparser('discover', 'pytest', subparsers)

        self.assertEqual(stub.calls, [
            ('subparsers.add_parser', None, {'name': 'pytest'}),
            ])

    def test_unsupported_command(self):
        subparsers = StubSubparsers(name=None)
        subparsers.return_add_parser = None

        with self.assertRaises(UnsupportedCommandError):
            add_cli_subparser('run', 'pytest', subparsers)
        with self.assertRaises(UnsupportedCommandError):
            add_cli_subparser('debug', 'pytest', subparsers)
        with self.assertRaises(UnsupportedCommandError):
            add_cli_subparser('???', 'pytest', subparsers)
        self.assertEqual(subparsers.calls, [
            ('add_parser', None, {'name': 'pytest'}),
            ('add_parser', None, {'name': 'pytest'}),
            ('add_parser', None, {'name': 'pytest'}),
            ])


class DiscoverTests(unittest.TestCase):

    DEFAULT_ARGS = [
        '-pno:terminal',
        '--collect-only',
        ]

    def test_basic(self):
        stub = Stub()
        stubpytest = StubPyTest(stub)
        plugin = StubPlugin(stub)
        expected = []
        plugin.discovered = expected

        parents, tests = discover([], _pytest_main=stubpytest.main, _plugin=plugin)

        self.assertEqual(parents, [])
        self.assertEqual(tests, expected)
        self.assertEqual(stub.calls, [
            ('pytest.main', None, {'args': self.DEFAULT_ARGS,
                                   'plugins': [plugin]}),
            ('discovered.parents', None, None),
            ('discovered.__len__', None, None),
            ('discovered.__getitem__', (0,), None),
            ])

    def test_failure(self):
        stub = Stub()
        pytest = StubPyTest(stub)
        pytest.return_main = 2
        plugin = StubPlugin(stub)

        with self.assertRaises(Exception):
            discover([], _pytest_main=pytest.main, _plugin=plugin)

        self.assertEqual(stub.calls, [
            ('pytest.main', None, {'args': self.DEFAULT_ARGS,
                                   'plugins': [plugin]}),
            ])


class CollectorTests(unittest.TestCase):

    def test_modifyitems(self):
        stub = Stub()
        discovered = StubDiscoveredTests(stub)
        session = StubPytestSession(stub)
        config = StubPytestConfig(stub)
        collector = TestCollector(tests=discovered)

        testroot = '/a/b/c'.replace('/', os.path.sep)
        relfile1 = './test_spam.py'.replace('/', os.path.sep)
        relfile2 = 'x/y/z/test_eggs.py'.replace('/', os.path.sep)

        collector.pytest_collection_modifyitems(session, config, [
            StubPytestItem(
                stub,
                nodeid='test_spam.py::SpamTests::test_one',
                name='test_one',
                location=('test_spam.py', 12, 'SpamTests.test_one'),
                fspath=os.path.join(testroot, 'test_spam.py'),
                function=FakeFunc('test_one'),
                ),
            StubPytestItem(
                stub,
                nodeid='test_spam.py::SpamTests::test_other',
                name='test_other',
                location=('test_spam.py', 19, 'SpamTests.test_other'),
                fspath=os.path.join(testroot, 'test_spam.py'),
                function=FakeFunc('test_other'),
                ),
            StubPytestItem(
                stub,
                nodeid='test_spam.py::test_all',
                name='test_all',
                location=('test_spam.py', 144, 'test_all'),
                fspath=os.path.join(testroot, 'test_spam.py'),
                function=FakeFunc('test_all'),
                ),
            StubPytestItem(
                stub,
                nodeid='test_spam.py::test_each[10-10]',
                name='test_each[10-10]',
                location=('test_spam.py', 273, 'test_each[10-10]'),
                fspath=os.path.join(testroot, 'test_spam.py'),
                function=FakeFunc('test_each'),
                ),
            StubPytestItem(
                stub,
                nodeid=relfile2 + '::All::BasicTests::test_first',
                name='test_first',
                location=(relfile2, 31, 'All.BasicTests.test_first'),
                fspath=os.path.join(testroot, relfile2),
                function=FakeFunc('test_first'),
                ),
            StubPytestItem(
                stub,
                nodeid=relfile2 + '::All::BasicTests::test_each[1+2-3]',
                name='test_each[1+2-3]',
                location=(relfile2, 62, 'All.BasicTests.test_each[1+2-3]'),
                fspath=os.path.join(testroot, relfile2),
                function=FakeFunc('test_each'),
                own_markers=[FakeMarker(v) for v in [
                    # supported
                    'skip', 'skipif', 'xfail',
                    # duplicate
                    'skip',
                    # ignored (pytest-supported)
                    'parameterize', 'usefixtures', 'filterwarnings',
                    # ignored (custom)
                    'timeout', 
                    ]],
                ),
            ])

        self.maxDiff = None
        self.assertEqual(stub.calls, [
            ('discovered.reset', None, None),
            ('discovered.add_test', None, dict(
                suiteids=['test_spam.py::SpamTests'],
                test=TestInfo(
                    id='test_spam.py::SpamTests::test_one',
                    name='test_one',
                    path=TestPath(
                        root=testroot,
                        relfile=relfile1,
                        func='SpamTests.test_one',
                        sub=None,
                        ),
                    lineno=12,
                    markers=None,
                    parentid='test_spam.py::SpamTests',
                    ),
                )),
            ('discovered.add_test', None, dict(
                suiteids=['test_spam.py::SpamTests'],
                test=TestInfo(
                    id='test_spam.py::SpamTests::test_other',
                    name='test_other',
                    path=TestPath(
                        root=testroot,
                        relfile=relfile1,
                        func='SpamTests.test_other',
                        sub=None,
                        ),
                    lineno=19,
                    markers=None,
                    parentid='test_spam.py::SpamTests',
                    ),
                )),
            ('discovered.add_test', None, dict(
                suiteids=[],
                test=TestInfo(
                    id='test_spam.py::test_all',
                    name='test_all',
                    path=TestPath(
                        root=testroot,
                        relfile=relfile1,
                        func='test_all',
                        sub=None,
                        ),
                    lineno=144,
                    markers=None,
                    parentid='test_spam.py',
                    ),
                )),
            ('discovered.add_test', None, dict(
                suiteids=[],
                test=TestInfo(
                    id='test_spam.py::test_each[10-10]',
                    name='test_each[10-10]',
                    path=TestPath(
                        root=testroot,
                        relfile=relfile1,
                        func='test_each',
                        sub=['[10-10]'],
                        ),
                    lineno=273,
                    markers=None,
                    parentid='test_spam.py::test_each',
                    ),
                )),
            ('discovered.add_test', None, dict(
                suiteids=[relfile2 + '::All',
                          relfile2 + '::All::BasicTests'],
                test=TestInfo(
                    id=relfile2 + '::All::BasicTests::test_first',
                    name='test_first',
                    path=TestPath(
                        root=testroot,
                        relfile=relfile2,
                        func='All.BasicTests.test_first',
                        sub=None,
                        ),
                    lineno=31,
                    markers=None,
                    parentid=relfile2 + '::All::BasicTests',
                    ),
                )),
            ('discovered.add_test', None, dict(
                suiteids=[relfile2 + '::All',
                          relfile2 + '::All::BasicTests'],
                test=TestInfo(
                    id=relfile2 + '::All::BasicTests::test_each[1+2-3]',
                    name='test_each[1+2-3]',
                    path=TestPath(
                        root=testroot,
                        relfile=relfile2,
                        func='All.BasicTests.test_each',
                        sub=['[1+2-3]'],
                        ),
                    lineno=62,
                    markers=['expected-failure', 'skip', 'skip-if'],
                    parentid=relfile2 + '::All::BasicTests::test_each',
                    ),
                )),
            ])

    def test_finish(self):
        stub = Stub()
        discovered = StubDiscoveredTests(stub)
        session = StubPytestSession(stub)
        testroot = '/a/b/c'.replace('/', os.path.sep)
        relfile = 'x/y/z/test_eggs.py'.replace('/', os.path.sep)
        session.items = [
            StubPytestItem(
                stub,
                nodeid=relfile + '::SpamTests::test_spam',
                name='test_spam',
                location=(relfile, 12, 'SpamTests.test_spam'),
                fspath=os.path.join(testroot, relfile),
                function=FakeFunc('test_spam'),
                ),
            ]
        collector = TestCollector(tests=discovered)

        collector.pytest_collection_finish(session)

        self.maxDiff = None
        self.assertEqual(stub.calls, [
            ('discovered.reset', None, None),
            ('discovered.add_test', None, dict(
                suiteids=[relfile + '::SpamTests'],
                test=TestInfo(
                    id=relfile + '::SpamTests::test_spam',
                    name='test_spam',
                    path=TestPath(
                        root=testroot,
                        relfile=relfile,
                        func='SpamTests.test_spam',
                        sub=None,
                        ),
                    lineno=12,
                    markers=None,
                    parentid=relfile + '::SpamTests',
                    ),
                )),
            ])

    def test_windows(self):
        stub = Stub()
        discovered = StubDiscoveredTests(stub)
        session = StubPytestSession(stub)
        testroot = r'c:\a\b\c'
        relfile = r'X\Y\Z\test_eggs.py'
        session.items = [
            StubPytestItem(
                stub,
                nodeid=relfile + '::SpamTests::test_spam',
                name='test_spam',
                location=('x/y/z/test_eggs.py', 12, 'SpamTests.test_spam'),
                fspath=testroot + '\\' + relfile,
                function=FakeFunc('test_spam'),
                ),
            ]
        collector = TestCollector(tests=discovered)
        if os.name != 'nt':
            def normcase(path):
                path = path.lower()
                return path.replace('/', '\\')
            collector.NORMCASE = normcase
            collector.PATHSEP = '\\'

        collector.pytest_collection_finish(session)

        self.maxDiff = None
        self.assertEqual(stub.calls, [
            ('discovered.reset', None, None),
            ('discovered.add_test', None, dict(
                suiteids=[relfile + '::SpamTests'],
                test=TestInfo(
                    id=relfile + '::SpamTests::test_spam',
                    name='test_spam',
                    path=TestPath(
                        root=testroot,
                        relfile=relfile,
                        func='SpamTests.test_spam',
                        sub=None,
                        ),
                    lineno=12,
                    markers=None,
                    parentid=relfile + '::SpamTests',
                    ),
                )),
            ])

    def test_imported_test(self):
        # pytest will even discover tests that were imported from
        # another module!
        stub = Stub()
        discovered = StubDiscoveredTests(stub)
        session = StubPytestSession(stub)
        testroot = '/a/b/c'.replace('/', os.path.sep)
        relfile = 'x/y/z/test_eggs.py'.replace('/', os.path.sep)
        srcfile = 'x/y/z/_extern.py'.replace('/', os.path.sep)
        session.items = [
            StubPytestItem(
                stub,
                nodeid=relfile + '::SpamTests::test_spam',
                name='test_spam',
                location=(srcfile, 12, 'SpamTests.test_spam'),
                fspath=os.path.join(testroot, relfile),
                function=FakeFunc('test_spam'),
                ),
            ]
        collector = TestCollector(tests=discovered)

        collector.pytest_collection_finish(session)

        self.maxDiff = None
        self.assertEqual(stub.calls, [
            ('discovered.reset', None, None),
            ('discovered.add_test', None, dict(
                suiteids=[relfile + '::SpamTests'],
                test=TestInfo(
                    id=relfile + '::SpamTests::test_spam',
                    name='test_spam',
                    path=TestPath(
                        root=testroot,
                        relfile=relfile,
                        func='SpamTests.test_spam',
                        sub=None,
                        ),
                    lineno=12,
                    markers=None,
                    parentid=relfile + '::SpamTests',
                    ),
                )),
            ])


class DiscoveredTestsTests(unittest.TestCase):

    def test_list(self):
        testroot = '/a/b/c'.replace('/', os.path.sep)
        relfile = 'test_spam.py'
        relfileid = os.path.join('.', relfile)
        tests = [
            TestInfo(
                id=relfile + '::test_each[10-10]',
                name='test_each[10-10]',
                path=TestPath(
                    root=testroot,
                    relfile=relfile,
                    func='test_each',
                    sub=['[10-10]'],
                    ),
                lineno=10,
                markers=None,
                parentid=relfile + '::test_each',
                ),
            TestInfo(
                id=relfile + '::All::BasicTests::test_first',
                name='test_first',
                path=TestPath(
                    root=testroot,
                    relfile=relfile,
                    func='All.BasicTests.test_first',
                    sub=None,
                    ),
                lineno=61,
                markers=None,
                parentid=relfile + '::All::BasicTests',
                ),
            ]
        allsuiteids = [
            [],
            [relfile + '::All',
             relfile + '::All::BasicTests',
             ],
            ]
        expected = [test._replace(id=os.path.join('.', test.id),
                                  parentid=os.path.join('.', test.parentid))
                    for test in tests]
        discovered = DiscoveredTests()
        for test, suiteids in zip(tests, allsuiteids):
            discovered.add_test(test, suiteids)
        size = len(discovered)
        items = [discovered[0], discovered[1]]
        snapshot = list(discovered)

        self.maxDiff = None
        self.assertEqual(size, 2)
        self.assertEqual(items, expected)
        self.assertEqual(snapshot, expected)

    def test_reset(self):
        testroot = '/a/b/c'.replace('/', os.path.sep)
        discovered = DiscoveredTests()
        discovered.add_test(
            TestInfo(
                id='test_spam.py::test_each',
                name='test_each',
                path=TestPath(
                    root=testroot,
                    relfile='test_spam.py',
                    func='test_each',
                    ),
                lineno=10,
                markers=[],
                parentid='test_spam.py',
                ),
            [])

        before = len(discovered), len(discovered.parents)
        discovered.reset()
        after = len(discovered), len(discovered.parents)

        self.assertEqual(before, (1, 2))
        self.assertEqual(after, (0, 0))

    def test_parents(self):
        testroot = '/a/b/c'.replace('/', os.path.sep)
        relfile = 'x/y/z/test_spam.py'.replace('/', os.path.sep)
        relfileid = os.path.join('.', relfile)
        tests = [
            TestInfo(
                id=relfile + '::test_each[10-10]',
                name='test_each[10-10]',
                path=TestPath(
                    root=testroot,
                    relfile=relfile,
                    func='test_each',
                    sub=['[10-10]'],
                    ),
                lineno=10,
                markers=None,
                parentid=relfile + '::test_each',
                ),
            TestInfo(
                id=relfile + '::All::BasicTests::test_first',
                name='test_first',
                path=TestPath(
                    root=testroot,
                    relfile=relfile,
                    func='All.BasicTests.test_first',
                    sub=None,
                    ),
                lineno=61,
                markers=None,
                parentid=relfile + '::All::BasicTests',
                ),
            ]
        allsuiteids = [
            [],
            [relfile + '::All',
             relfile + '::All::BasicTests',
             ],
            ]
        discovered = DiscoveredTests()
        for test, suiteids in zip(tests, allsuiteids):
            discovered.add_test(test, suiteids)

        parents = discovered.parents

        self.maxDiff = None
        self.assertEqual(parents, [
            ParentInfo(
                id='.',
                kind='folder',
                name=testroot,
                ),
            ParentInfo(
                id='./x'.replace('/', os.path.sep),
                kind='folder',
                name='x',
                root=testroot,
                parentid='.',
                ),
            ParentInfo(
                id='./x/y'.replace('/', os.path.sep),
                kind='folder',
                name='y',
                root=testroot,
                parentid='./x'.replace('/', os.path.sep),
                ),
            ParentInfo(
                id='./x/y/z'.replace('/', os.path.sep),
                kind='folder',
                name='z',
                root=testroot,
                parentid='./x/y'.replace('/', os.path.sep),
                ),
            ParentInfo(
                id=relfileid,
                kind='file',
                name=os.path.basename(relfile),
                root=testroot,
                parentid=os.path.dirname(relfileid),
                ),
            ParentInfo(
                id=relfileid + '::All',
                kind='suite',
                name='All',
                root=testroot,
                parentid=relfileid,
                ),
            ParentInfo(
                id=relfileid + '::All::BasicTests',
                kind='suite',
                name='BasicTests',
                root=testroot,
                parentid=relfileid + '::All',
                ),
            ParentInfo(
                id=relfileid + '::test_each',
                kind='function',
                name='test_each',
                root=testroot,
                parentid=relfileid,
                ),
            ])

    def test_add_test_simple(self):
        testroot = '/a/b/c'.replace('/', os.path.sep)
        test = TestInfo(
            id='test_spam.py::test_spam',
            name='test_spam',
            path=TestPath(
                root=testroot,
                relfile='test_spam.py',
                func='test_spam',
                ),
            lineno=11,
            markers=[],
            parentid='test_spam.py',
            )
        expected = test._replace(id=os.path.join('.', test.id),
                                 parentid=os.path.join('.', test.parentid))
        discovered = DiscoveredTests()

        before = list(discovered), discovered.parents
        discovered.add_test(test, [])
        after = list(discovered), discovered.parents

        self.maxDiff = None
        self.assertEqual(before, ([], []))
        self.assertEqual(after, ([expected], [
            ParentInfo(
                id='.',
                kind='folder',
                name=testroot,
                ),
            ParentInfo(
                id=os.path.join('.', 'test_spam.py'),
                kind='file',
                name='test_spam.py',
                root=testroot,
                parentid='.',
                ),
            ]))

    def test_multiroot(self):
        # the first root
        testroot1 = '/a/b/c'.replace('/', os.path.sep)
        relfile1 = 'test_spam.py'
        relfileid1 = os.path.join('.', relfile1)
        alltests = [
            TestInfo(
                id=relfile1 + '::test_spam',
                name='test_spam',
                path=TestPath(
                    root=testroot1,
                    relfile=relfile1,
                    func='test_spam',
                    ),
                lineno=10,
                markers=[],
                parentid=relfile1,
                ),
            ]
        allsuiteids = [
            [],
            ]
        # the second root
        testroot2 = '/x/y/z'.replace('/', os.path.sep)
        relfile2 = 'w/test_eggs.py'
        relfileid2 = os.path.join('.', relfile2)
        alltests.extend([
            TestInfo(
                id=relfile2 + 'BasicTests::test_first',
                name='test_first',
                path=TestPath(
                    root=testroot2,
                    relfile=relfile2,
                    func='BasicTests.test_first',
                    ),
                lineno=61,
                markers=[],
                parentid=relfile2 + '::BasicTests',
                ),
            ])
        allsuiteids.extend([
            [relfile2 + '::BasicTests',
             ],
            ])

        discovered = DiscoveredTests()
        for test, suiteids in zip(alltests, allsuiteids):
            discovered.add_test(test, suiteids)
        tests = list(discovered)
        parents = discovered.parents

        self.maxDiff = None
        self.assertEqual(tests, [
            # the first root
            TestInfo(
                id=relfileid1 + '::test_spam',
                name='test_spam',
                path=TestPath(
                    root=testroot1,
                    relfile=relfile1,
                    func='test_spam',
                    ),
                lineno=10,
                markers=[],
                parentid=relfileid1,
                ),
            # the secondroot
            TestInfo(
                id=relfileid2 + 'BasicTests::test_first',
                name='test_first',
                path=TestPath(
                    root=testroot2,
                    relfile=relfile2,
                    func='BasicTests.test_first',
                    ),
                lineno=61,
                markers=[],
                parentid=relfileid2 + '::BasicTests',
                ),
            ])
        self.assertEqual(parents, [
            # the first root
            ParentInfo(
                id='.',
                kind='folder',
                name=testroot1,
                ),
            ParentInfo(
                id=relfileid1,
                kind='file',
                name=os.path.basename(relfile1),
                root=testroot1,
                parentid=os.path.dirname(relfileid1),
                ),
            # the secondroot
            ParentInfo(
                id='.',
                kind='folder',
                name=testroot2,
                ),
            ParentInfo(
                id='./w'.replace('/', os.path.sep),
                kind='folder',
                name='w',
                root=testroot2,
                parentid='.',
                ),
            ParentInfo(
                id=relfileid2,
                kind='file',
                name=os.path.basename(relfile2),
                root=testroot2,
                parentid=os.path.dirname(relfileid2),
                ),
            ParentInfo(
                id=relfileid2 + '::BasicTests',
                kind='suite',
                name='BasicTests',
                root=testroot2,
                parentid=relfileid2,
                ),
            ])
