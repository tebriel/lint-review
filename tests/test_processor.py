
from . import load_fixture, fixer_ini, create_pull_files
from unittest import TestCase
from lintreview.config import build_review_config
from lintreview.diff import DiffCollection
from lintreview.processor import Processor
from lintreview.repo import GithubPullRequest
from lintreview.fixers.error import ConfigurationError, WorkflowError
from github3.pulls import PullRequest
from github3.session import GitHubSession
from mock import patch, sentinel, Mock, ANY
import json


app_config = {
    'GITHUB_AUTHOR_NAME': 'bot',
    'GITHUB_AUTHOR_EMAIL': 'bot@example.com',
    'SUMMARY_THRESHOLD': 50,
}


class TestProcessor(TestCase):

    def setUp(self):
        self.session = GitHubSession()

    def get_pull_request(self):
        fixture = load_fixture('pull_request.json')
        model = PullRequest(json.loads(fixture)['pull_request'], self.session)

        files = load_fixture('one_file_pull_request.json')
        model.files = lambda: create_pull_files(files)

        return GithubPullRequest(model)

    def test_load_changes(self):
        pull = self.get_pull_request()
        repo = Mock()

        config = build_review_config('', app_config)
        subject = Processor(repo, pull, './tests', config)
        subject.load_changes()

        self.assertEqual(1, len(subject._changes), 'File count is wrong')
        assert isinstance(subject._changes, DiffCollection)

    def test_run_tools__no_changes(self):
        pull = self.get_pull_request()
        repo = Mock()

        config = build_review_config('', app_config)
        subject = Processor(repo, pull, './tests', config)
        self.assertRaises(RuntimeError,
                          subject.run_tools)

    @patch('lintreview.processor.tools')
    @patch('lintreview.processor.fixers')
    def test_run_tools__ignore_patterns(self, fixer_stub, tool_stub):
        pull = self.get_pull_request()
        repo = Mock()

        config = build_review_config(fixer_ini, app_config)
        config.ignore_patterns = lambda: [
            'View/Helper/*']

        subject = Processor(repo, pull, './tests', config)
        subject.load_changes()
        subject.run_tools()
        tool_stub.run.assert_called_with(
            ANY,
            [],
            ANY)

    @patch('lintreview.processor.tools')
    @patch('lintreview.processor.fixers')
    def test_run_tools__execute_fixers(self, fixer_stub, tool_stub):
        pull = self.get_pull_request()
        repo = Mock()

        tool_stub.factory.return_value = sentinel.tools

        fixer_stub.create_context.return_value = sentinel.context
        fixer_stub.run_fixers.return_value = sentinel.diff

        config = build_review_config(fixer_ini, app_config)
        subject = Processor(repo, pull, './tests', config)
        subject.load_changes()
        subject.run_tools()

        file_path = 'View/Helper/AssetCompressHelper.php'
        fixer_stub.create_context.assert_called_with(
            config,
            './tests',
            repo,
            pull)
        fixer_stub.run_fixers.assert_called_with(
            sentinel.tools,
            './tests',
            [file_path])
        fixer_stub.apply_fixer_diff.assert_called_with(
            subject._changes,
            sentinel.diff,
            sentinel.context)
        assert tool_stub.run.called, 'Should have ran'

    @patch('lintreview.processor.tools')
    @patch('lintreview.processor.fixers')
    def test_run_tools__execute_fixers_fail(self, fixer_stub, tool_stub):
        pull = self.get_pull_request()
        repo = Mock()

        tool_stub.factory.return_value = sentinel.tools

        fixer_stub.create_context.return_value = sentinel.context
        fixer_stub.run_fixers.side_effect = RuntimeError

        config = build_review_config(fixer_ini, app_config)
        subject = Processor(repo, pull, './tests', config)
        subject.load_changes()
        subject.run_tools()

        assert fixer_stub.create_context.called
        assert fixer_stub.run_fixers.called
        self.assertFalse(fixer_stub.apply_fixer_diff.called)
        self.assertTrue(fixer_stub.rollback_changes.called,
                        'Runtime error should trigger git reset.')
        assert tool_stub.run.called, 'Should have ran'

    def test_run_tools__fixer_errors(self):
        error_message = 'A bad thing'
        cases = (
            WorkflowError(error_message),
            ConfigurationError(error_message)
        )
        for case in cases:
            yield self._test_run_tools_fixer_error_scenario, case

    @patch('lintreview.processor.tools')
    @patch('lintreview.processor.fixers')
    def _test_run_tools_fixer_error_scenario(self, error,
                                             fixer_stub, tool_stub):
        pull = self.get_pull_request()
        repo = Mock()

        tool_stub.factory.return_value = sentinel.tools

        fixer_stub.create_context.return_value = sentinel.context
        fixer_stub.apply_fixer_diff.side_effect = error

        config = build_review_config(fixer_ini, app_config)
        subject = Processor(repo, pull, './tests', config)
        subject.load_changes()
        subject.run_tools()

        assert fixer_stub.create_context.called
        assert fixer_stub.run_fixers.called
        assert tool_stub.run.called, 'Should have ran'
        self.assertFalse(fixer_stub.rollback_changes.called,
                         'No rollback on strategy failure')
        self.assertEqual(1, len(subject.problems), 'strategy error adds pull comment')
        self.assertEqual('Unable to apply fixers. ' + str(error),
                         subject.problems.all()[0].body)

    def test_publish(self):
        pull = self.get_pull_request()
        repo = Mock()

        config = build_review_config(fixer_ini, app_config)
        subject = Processor(repo, pull, './tests', config)
        subject.problems = Mock()
        subject._review = Mock()

        subject.publish()
        self.assertTrue(subject.problems.limit_to_changes.called,
                        'Problems should be filtered.')
        self.assertTrue(subject._review.publish_review.called,
                        'Review should be published.')
        subject._review.publish_review.assert_called_with(
            subject.problems,
            pull.head)

    def test_publish_checkrun(self):
        pull = self.get_pull_request()
        repo = Mock()

        config = build_review_config(fixer_ini, app_config)
        subject = Processor(repo, pull, './tests', config)
        subject.problems = Mock()
        subject._review = Mock()

        subject.publish(check_run_id=9)
        self.assertEqual(True,
                         subject.problems.limit_to_changes.called,
                         'Problems should be filtered.')
        self.assertEqual(True,
                         subject._review.publish_checkrun.called,
                         'Review should be published.')
        subject._review.publish_checkrun.assert_called_with(
            subject.problems,
            9)
