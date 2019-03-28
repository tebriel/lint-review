from lintreview import web
from mock import patch, Mock
from unittest import TestCase
import json

test_data = {
    'action': 'derp',
    'pull_request': {
        'number': '3',
        'head': {
            'ref': 'master',
            "sha": "53cb70abadcb3237dcb2aa2b1f24dcf7bcc7d68e",
            'repo': {
                'clone_url': 'https://github.com/contributor/lint-test.git',
                'git_url': 'git://github.com/other/testing',
                'name': 'testing',
                'owner': {
                    'login': 'other',
                },
            },
        },
        'base': {
            'ref': 'master',
            'repo': {
                'clone_url': 'https://github.com/contributor/lint-test.git',
                'name': 'testing',
                'git_url': 'git://github.com/mark/testing',
                'owner': {
                    'login': 'mark',
                },
            },
        },
    },
}


class WebTest(TestCase):

    def setUp(self):
        self.app = web.app.test_client()

    def test_ping(self):
        res = self.app.get('/ping')
        self.assertEqual("lint-review: {} pong\n".format(web.version),
                         res.data.decode('utf-8'))

    def test_start_request_no_get(self):
        res = self.app.get('/review/start')
        self.assertEqual(405, res.status_code)

    def test_start_request__json_fail(self):
        data = {'herp': 'derp'}
        data = json.dumps(data)
        res = self.app.post('/review/start',
                            content_type='application/json',
                            data=data,
                            headers={
                                'X-Github-Event': 'pull_request'
                            })
        self.assertEqual(403, res.status_code)

    @patch('lintreview.web.process_pull_request')
    def test_start_request__ignore_unknown_action(self, task):
        cases = ('closed', 'labeled', 'assigned')
        for action in cases:
            payload = test_data.copy()
            payload['action'] = action
            data = json.dumps(payload)
            res = self.app.post('/review/start',
                                content_type='application/json',
                                data=data,
                                headers={
                                    'X-Github-Event': 'pull_request'
                                })
            self.assertEqual(204, res.status_code)
            self.assertEqual('', res.data.decode('utf-8'))
            self.assertFalse(task.called)

    @patch('lintreview.web.get_lintrc')
    @patch('lintreview.web.process_pull_request')
    def test_start_request_fail_on_lint_rc_file(self, task, lintrc):
        lintrc.side_effect = IOError()

        data = json.dumps(test_data)
        self.app.post('/review/start',
                      content_type='application/json',
                      data=data,
                      headers={
                          'X-Github-Event': 'pull_request'
                      })
        self.assertFalse(task.called, 'No task should have been queued')

    @patch('lintreview.web.get_repository')
    @patch('lintreview.web.get_lintrc')
    @patch('lintreview.web.process_pull_request')
    def test_start_review_schedule_job(self, task, lintrc, get_repo):
        get_repo.return_value = Mock()

        opened = test_data.copy()
        opened['action'] = 'opened'
        data = json.dumps(opened)

        lintrc.return_value = """
[tools]
linters = pep8"""

        res = self.app.post('/review/start',
                            content_type='application/json',
                            data=data,
                            headers={
                                'X-Github-Event': 'pull_request'
                            })
        self.assertTrue(task.delay.called, 'Process request should be called')
        self.assertEqual(204, res.status_code)
        self.assertEqual('', res.data.decode('utf-8'))

    @patch('lintreview.web.get_repository')
    @patch('lintreview.web.get_lintrc')
    @patch('lintreview.web.process_pull_request')
    def test_start_review_schedule_job__on_reopened(self, task, lintrc,
                                                    get_repo):
        get_repo.return_value = Mock()
        reopened = test_data.copy()
        reopened['action'] = 'reopened'
        data = json.dumps(reopened)

        lintrc.return_value = """
[tools]
linters = pep8"""

        res = self.app.post('/review/start',
                            content_type='application/json',
                            data=data,
                            headers={
                                'X-Github-Event': 'pull_request'
                            })
        self.assertTrue(task.delay.called, 'Process request should be called')
        self.assertEqual(204, res.status_code)
        self.assertEqual('', res.data.decode('utf-8'))

    @patch('lintreview.web.get_repository')
    @patch('lintreview.web.GithubRepository')
    @patch('lintreview.web.get_lintrc')
    @patch('lintreview.web.process_pull_request')
    def test_handle_check_suite_event(self, task, lintrc, gh_repo, get_repo):
        """Test that we can handle the check_suite event type."""
        with open('tests/fixtures/check_suite.json') as cs_json:
            check_suite_event = cs_json.read()

        get_repo().pull_request().head = 'abc123'
        gh_repo().pull_request().head = 'abc123'
        lintrc.return_value = """
[tools]
linters = pep8"""

        res = self.app.post('/review/start',
                            content_type='application/json',
                            data=check_suite_event,
                            headers={
                                'X-Github-Event': 'check_suite'
                            })
        self.assertEqual(204, res.status_code)
        self.assertTrue(task.delay.called, 'Process request should be called')
