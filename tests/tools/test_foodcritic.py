import os

from lintreview.review import Comment, Problems
from lintreview.tools.foodcritic import Foodcritic
from unittest import TestCase
from tests import root_dir
import pytest


class TestFoodcritic(TestCase):

    fixtures = [
        'tests/fixtures/foodcritic/noerrors',
        'tests/fixtures/foodcritic/errors',
    ]

    def setUp(self):
        self.problems = Problems()

    @pytest.mark.requires_linters
    def test_process_cookbook_pass__no_path(self):
        self.tool = Foodcritic(self.problems,
                               {},
                               os.path.join(root_dir, self.fixtures[0]))
        self.tool.process_files(None)
        self.assertEqual([], self.problems.all())

    @pytest.mark.requires_linters
    def test_process_cookbook_pass(self):
        self.tool = Foodcritic(self.problems,
                               {'path': self.fixtures[0]},
                               root_dir)
        self.tool.process_files(None)
        self.assertEqual([], self.problems.all())

    @pytest.mark.requires_linters
    def test_process_cookbook_fail(self):
        self.tool = Foodcritic(self.problems,
                               {'path': self.fixtures[1]},
                               root_dir)
        self.tool.process_files(None)
        problems = self.problems.all()
        self.assertEqual(5, len(problems))

        expected = Comment(
            'tests/fixtures/foodcritic/errors/recipes/apache2.rb', 1, 1,
            'FC007: Ensure recipe dependencies are reflected in cookbook '
            'metadata')
        self.assertEqual(expected, problems[1])
