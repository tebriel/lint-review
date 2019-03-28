
from lintreview.review import Comment, Problems
from lintreview.tools.credo import Credo
from unittest import TestCase
from tests import root_dir
import pytest


class TestCredo(TestCase):

    fixtures = [
        'tests/fixtures/credo/no_errors.ex',
        'tests/fixtures/credo/has_errors.ex',
    ]

    def setUp(self):
        self.problems = Problems()
        self.tool = Credo(self.problems, {}, root_dir)

    def test_match_file(self):
        self.assertFalse(self.tool.match_file('test.php'))
        self.assertFalse(self.tool.match_file('test.js'))
        self.assertFalse(self.tool.match_file('dir/name/test.js'))
        self.assertTrue(self.tool.match_file('test.ex'))
        self.assertTrue(self.tool.match_file('test.exs'))
        self.assertTrue(self.tool.match_file('dir/name/test.ex'))
        self.assertTrue(self.tool.match_file('dir/name/test.exs'))

    @pytest.mark.requires_linters
    def test_process_files__one_file_pass(self):
        self.tool.process_files([self.fixtures[0]])
        self.assertEqual([], self.problems.all(self.fixtures[0]))

    @pytest.mark.requires_linters
    def test_process_files__one_file_fail(self):
        self.tool.process_files([self.fixtures[1]])
        problems = self.problems.all(self.fixtures[1])
        self.assertEqual(2, len(problems))
        fname = self.fixtures[1]
        expected = Comment(fname, 3, 3, 'Pipe chain should start with a raw value.')
        self.assertEqual(expected, problems[0])
        expected = Comment(fname, 1, 1, 'Modules should have a @moduledoc tag.')
        self.assertEqual(expected, problems[1])
