from unittest import TestCase
from lintreview.review import Problems
from lintreview.tools.gpg import Gpg
from tests import root_dir

import pytest


class TestGpg(TestCase):

    def setUp(self):
        self.problems = Problems()
        self.tool = Gpg(self.problems, {}, root_dir)

    @pytest.mark.requires_linters
    def test_check_dependencies(self):
        self.assertEqual(True, self.tool.check_dependencies())

    @pytest.mark.requires_linters
    def test_execute(self):
        self.tool.execute_commits([])

        comments = self.problems.all()
        if len(comments):
            self.assertIn('gpg signature', comments[0].body)
