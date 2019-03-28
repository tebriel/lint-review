from unittest import TestCase

from lintreview.review import Problems, Comment, IssueComment
from lintreview.tools.eslint import Eslint
import lintreview.docker as docker
from mock import patch, call, ANY
from tests import root_dir, read_file, read_and_restore_file

import pytest


FILE_WITH_NO_ERRORS = 'tests/fixtures/eslint/no_errors.js'
FILE_WITH_ERRORS = 'tests/fixtures/eslint/has_errors.js'
FILE_WITH_FIXER_ERRORS = 'tests/fixtures/eslint/fixer_errors.js'


class TestEslint(TestCase):

    def setUp(self):
        self.problems = Problems()
        options = {
            'config': 'tests/fixtures/eslint/recommended_config.json'
        }
        self.tool = Eslint(self.problems, options, root_dir)

    def test_match_file(self):
        self.assertFalse(self.tool.match_file('test.php'))
        self.assertFalse(self.tool.match_file('dir/name/test.py'))
        self.assertFalse(self.tool.match_file('test.py'))
        self.assertTrue(self.tool.match_file('test.js'))
        self.assertTrue(self.tool.match_file('test.jsx'))
        self.assertTrue(self.tool.match_file('dir/name/test.js'))

    def test_match_file__extensions(self):
        options = {
            'extensions': '.js,.jsm'
        }
        tool = Eslint(self.problems, options)
        self.assertFalse(tool.match_file('test.php'))
        self.assertFalse(tool.match_file('test.jsx'))
        self.assertTrue(tool.match_file('test.js'))
        self.assertTrue(tool.match_file('test.jsm'))

    @patch('lintreview.tools.eslint.docker')
    def test_pre_flight(self, mock_docker):
        options = {
            'preflight_cmd': 'make uilib',
            'preflight_dir': 'apollo_app, iam_app'
        }
        tool = Eslint(self.problems, options, root_dir)
        tool.pre_flight_command()
        self.assertEqual(2, mock_docker.run.call_count)
        expected_apollo = call(
            'eslint',
            ['make', 'uilib'],
            source_dir=ANY,
            workdir=ANY,
        )
        expected_iam = call(
            'eslint',
            ['make', 'uilib'],
            source_dir=ANY,
            workdir=ANY,
        )
        mock_docker.run.assert_has_calls([expected_apollo, expected_iam], any_order=True)

    @pytest.mark.requires_linters
    def test_check_dependencies(self):
        self.assertTrue(self.tool.check_dependencies())

    @pytest.mark.requires_linters
    def test_process_files_pass(self):
        self.tool.process_files([FILE_WITH_NO_ERRORS])
        actual = self.problems.all(FILE_WITH_NO_ERRORS)
        self.assertEqual([], actual)

    @pytest.mark.requires_linters
    def test_process_files_fail(self):
        self.tool.process_files([FILE_WITH_ERRORS])
        problems = self.problems.all(FILE_WITH_ERRORS)
        self.assertEqual(2, len(problems))

        msg = ("'foo' is assigned a value but never used. (no-unused-vars) (eslint.rules.no-unused-vars)\n"
               "'bar' is not defined. (no-undef) (eslint.rules.no-undef)")
        expected = Comment(FILE_WITH_ERRORS, 2, 2, msg)
        self.assertEqual(expected, problems[0])

        msg = "'alert' is not defined. (no-undef) (eslint.rules.no-undef)"
        expected = Comment(FILE_WITH_ERRORS, 4, 4, msg)
        self.assertEqual(expected, problems[1])

    @pytest.mark.requires_linters
    def test_process_files__config_file_missing(self):
        tool = Eslint(self.problems,
                      options={'config': 'invalid-file'},
                      base_path=root_dir)
        tool.process_files([FILE_WITH_ERRORS])
        problems = self.problems.all()
        self.assertEqual(1, len(problems), 'Invalid config returns 1 error')
        msg = ('Your eslint config file is missing or invalid. '
               'Please ensure that `invalid-file` exists and is valid.')
        expected = [IssueComment(msg)]
        self.assertEqual(expected, problems)

    @pytest.mark.requires_linters
    def test_process_files__config_file_syntax_error(self):
        tool = Eslint(self.problems,
                      options={
                          'config': 'tests/fixtures/eslint/syntaxerror.yaml'
                      },
                      base_path=root_dir)
        tool.process_files([FILE_WITH_ERRORS])
        problems = self.problems.all()
        self.assertEqual(1, len(problems), 'Invalid config returns 1 error')
        self.assertIn('Your ESLint configuration is not valid', problems[0].body)
        self.assertIn('YAMLException: Cannot read', problems[0].body)

    @pytest.mark.requires_linters
    def test_process_files_uses_default_config(self):
        tool = Eslint(self.problems, options={}, base_path=root_dir)
        tool.process_files([FILE_WITH_ERRORS])
        problems = self.problems.all(FILE_WITH_ERRORS)
        self.assertEqual(2, len(problems), 'With no config file there should be errors.')

    @pytest.mark.requires_linters
    def test_process_files__invalid_config(self):
        options = {'config': 'tests/fixtures/eslint/invalid.json'}
        tool = Eslint(self.problems, options, root_dir)
        tool.process_files([FILE_WITH_ERRORS])
        problems = self.problems.all()
        self.assertEqual(1, len(problems), 'Invalid config should report an error')
        error = problems[0]
        self.assertIn('Your eslint configuration output the following error', error.body)
        self.assertIn("Cannot find module 'eslint-config-invalid-rules'", error.body)

    @pytest.mark.requires_linters
    def test_process_files__missing_plugin(self):
        options = {'config': 'tests/fixtures/eslint/missingplugin.json'}
        tool = Eslint(self.problems, options, root_dir)
        tool.process_files([FILE_WITH_ERRORS])
        problems = self.problems.all()
        self.assertEqual(1, len(problems), 'Invalid config should report an error')
        error = problems[0]
        self.assertIn('Your eslint configuration output the following error', error.body)
        self.assertIn('ESLint couldn\'t find the plugin "eslint-plugin-nopers"', error.body)

    @pytest.mark.requires_linters
    def test_process_files__deprecated_option(self):
        options = {'config': 'tests/fixtures/eslint/deprecatedoption.json'}
        tool = Eslint(self.problems, options, root_dir)
        tool.process_files([FILE_WITH_ERRORS])
        problems = self.problems.all()
        self.assertGreater(len(problems), 0, 'Invalid config should report an error')
        error = problems[0]
        self.assertIn('Your eslint configuration output the following error', error.body)
        self.assertIn('DeprecationWarning', error.body)
        style_error = problems[1]
        self.assertNotIn('DeprecationWarning', style_error.body)

    @pytest.mark.requires_linters
    def test_process_files_with_config(self):
        options = {
            'config': 'tests/fixtures/eslint/config.json'
        }
        tool = Eslint(self.problems, options, root_dir)
        tool.process_files([FILE_WITH_ERRORS])

        problems = self.problems.all(FILE_WITH_ERRORS)

        msg = ("'foo' is assigned a value but never used. (no-unused-vars) (eslint.rules.no-unused-vars)\n"
               "'bar' is not defined. (no-undef) (eslint.rules.no-undef)\n"
               "Missing semicolon. (semi) (eslint.rules.semi)")
        expected = [Comment(FILE_WITH_ERRORS, 2, 2, msg)]
        self.assertEqual(expected, problems)

    def test_has_fixer__not_enabled(self):
        tool = Eslint(self.problems, {})
        self.assertEqual(False, tool.has_fixer())

    def test_has_fixer__enabled(self):
        tool = Eslint(self.problems, {'fixer': True}, root_dir)
        self.assertEqual(True, tool.has_fixer())

    @pytest.mark.requires_linters
    def test_execute_fixer(self):
        tool = Eslint(self.problems, {
            'config': 'tests/fixtures/eslint/recommended_config.json',
            'fixer': True,
        }, root_dir)
        original = read_file(FILE_WITH_FIXER_ERRORS)
        tool.execute_fixer([FILE_WITH_FIXER_ERRORS])

        updated = read_and_restore_file(FILE_WITH_FIXER_ERRORS, original)
        assert original != updated, 'File content should change.'
        self.assertEqual(0, len(self.problems.all()), 'No errors should be recorded')

    @pytest.mark.requires_linters
    def test_execute_fixer__no_problems_remain(self):
        tool = Eslint(self.problems, {
            'config': 'tests/fixtures/eslint/recommended_config.json',
            'fixer': True
        }, root_dir)

        # The fixture file can have all problems fixed by eslint
        original = read_file(FILE_WITH_FIXER_ERRORS)
        tool.execute_fixer([FILE_WITH_FIXER_ERRORS])
        tool.process_files([FILE_WITH_FIXER_ERRORS])

        read_and_restore_file(FILE_WITH_FIXER_ERRORS, original)
        self.assertEqual(0, len(self.problems.all()), 'All errors should be autofixed')

    @pytest.mark.requires_linters
    def test_execute__install_plugins(self):
        custom_dir = root_dir + '/tests/fixtures/eslint_custom'
        tool = Eslint(self.problems, {
            'config': 'config.json',
            'install_plugins': True,
            'fixer': True
        }, custom_dir)
        target = 'has_errors.js'
        tool.process_files([target])

        problems = self.problems.all()
        self.assertEqual(2, len(problems), 'Should find errors')
        self.assertIn('Unexpected var', problems[0].body)

        self.assertTrue(docker.image_exists('nodejs'), 'original image is present')
        self.assertNotIn('eslint-', docker.images(), 'no eslint image remains')

    @pytest.mark.requires_linters
    def test_execute_fixer__install_plugins(self):
        custom_dir = root_dir + '/tests/fixtures/eslint_custom'
        tool = Eslint(self.problems, {
            'config': 'config.json',
            'install_plugins': True,
            'fixer': True
        }, custom_dir)

        target = 'tests/fixtures/eslint_custom/fixer_errors.js'

        # The fixture file can have all problems fixed by eslint
        original = read_file(target)
        tool.execute_fixer(['fixer_errors.js'])
        tool.process_files(['fixer_errors.js'])

        read_and_restore_file(target, original)
        self.assertEqual(0, len(self.problems.all()), 'All errors should be autofixed')
        self.assertNotIn('eslint-', docker.images(), 'no eslint image remains')

    @pytest.mark.requires_linters
    def test_execute__install_plugins_cleanup_image_on_failure(self):
        custom_dir = root_dir + '/tests/fixtures/eslint_custom'
        tool = Eslint(self.problems, {
            'config': 'invalid.json',
            'install_plugins': True,
            'fixer': True
        }, custom_dir)
        target = 'has_errors.js'
        tool.process_files([target])

        problems = self.problems.all()
        self.assertEqual(1, len(problems))
        self.assertIn('Cannot find module', problems[0].body)

        self.assertTrue(docker.image_exists('eslint'), 'original image is present')
        self.assertNotIn('eslint-', docker.images(), 'no eslint image remains')
