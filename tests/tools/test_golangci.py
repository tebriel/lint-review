from lintreview.review import Problems, Comment
from lintreview.tools.golangci import Golangci
from unittest import TestCase
from mock import patch, call
from tests import root_dir, read_file, read_and_restore_file
import pytest


class TestGolangCI(TestCase):

    fixtures = [
        'tests/fixtures/golangci-lint/no_errors.go',
        'tests/fixtures/golangci-lint/has_errors.go',
        'tests/fixtures/golangci-lint/http.go',
    ]

    def setUp(self):
        self.problems = Problems()
        self.tool = Golangci(self.problems, {}, root_dir)

    def test_match_file(self):
        self.assertTrue(self.tool.match_file('test.go'))
        self.assertTrue(self.tool.match_file('dir/name/test.go'))
        self.assertFalse(self.tool.match_file('dir/name/test.py'))
        self.assertFalse(self.tool.match_file('test.php'))
        self.assertFalse(self.tool.match_file('test.golp'))

    @pytest.mark.requires_linters
    def test_check_dependencies(self):
        self.assertTrue(self.tool.check_dependencies())

    @pytest.mark.requires_linters
    def test_process_files__one_file_pass(self):
        self.tool.process_files([self.fixtures[0]])
        self.assertEqual([], self.problems.all(self.fixtures[0]))

    @pytest.mark.requires_linters
    def test_process_files__one_file_fail(self):
        self.tool.process_files([self.fixtures[1]])
        problems = self.problems.all(self.fixtures[1])
        self.assertEqual(4, len(problems))

        fname = self.fixtures[1]
        expected = Comment(
            fname,
            9,
            9,
            'method is missing receiver (typecheck)')
        self.assertIn(expected, problems)

        expected = Comment(
            fname,
            6,
            6,
            '"os" imported but not used (typecheck)')
        self.assertIn(expected, problems)

    @pytest.mark.requires_linters
    def test_process_files_two_files(self):
        self.tool.process_files([self.fixtures[0], self.fixtures[1]])

        self.assertEqual([], self.problems.all(self.fixtures[0]))

        problems = self.problems.all(self.fixtures[1])
        self.assertGreaterEqual(len(problems), 2)

    @pytest.mark.requires_linters
    def test_process_files_in_different_packages(self):
        self.tool.process_files([self.fixtures[1], self.fixtures[2]])

        problems = self.problems.all()
        self.assertGreaterEqual(len(problems), 4)
        self.assertGreaterEqual(len(self.problems.all(self.fixtures[1])), 3)
        self.assertGreaterEqual(len(self.problems.all(self.fixtures[2])), 1)

    @pytest.mark.requires_linters
    @patch('lintreview.docker.run')
    def test_process_files_with_config__mocked(self, mock_command):
        mock_command.return_value = ""
        config = {
            'config': 'path/to/golangci.yml',
            'go111module': '1',
        }
        tool = Golangci(self.problems, config, root_dir)
        tool.process_files([self.fixtures[1]])

        expected = call(
            'golangci-lint',
            command=[
                'golangci-lint',
                'run',
                '--out-format=checkstyle',
                '--config',
                '/src/path/to/golangci.yml',
                self.fixtures[1]
            ],
            source_dir=tool.base_path,
            env={'GO111MODULE': 'on'},
            include_error=False,
        )

        self.assertEqual(expected, mock_command.call_args, 'Configuration was not applied correctly.')

    @pytest.mark.requires_linters
    def test_process_files_with_config(self):
        config = {
            'config': 'tests/fixtures/golangci-lint/golangci.yml',
        }
        tool = Golangci(self.problems, config, root_dir)
        tool.process_files([self.fixtures[1]])
        self.assertEqual(4, len(self.problems))

    def test_has_fixer__not_enabled(self):
        tool = Golangci(self.problems, {})
        self.assertEqual(False, tool.has_fixer())

    def test_has_fixer__enabled(self):
        tool = Golangci(self.problems, {'fixer': True})
        self.assertEqual(True, tool.has_fixer())

    @pytest.mark.requires_linters
    def test_execute_fixer(self):
        config = {
            'fixer': True,
            'config': 'tests/fixtures/golangci-lint/golangci-fixer.yml',
        }
        tool = Golangci(self.problems, config, root_dir)

        original = read_file(self.fixtures[1])
        tool.execute_fixer(self.fixtures)

        updated = read_and_restore_file(self.fixtures[1], original)
        assert original != updated, 'File content should change.'
        self.assertEqual(0, len(self.problems.all()), 'No errors should be recorded')
