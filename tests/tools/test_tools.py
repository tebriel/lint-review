from unittest import TestCase
from mock import Mock

import lintreview.tools as tools
from lintreview.config import ReviewConfig, build_review_config
from lintreview.review import Review, Problems
from lintreview.tools import pep8, jshint
from tests import root_dir, fixtures_path

import pytest
import github3


sample_ini = """
[tools]
linters = pep8, jshint

[tool_jshint]
config = ./jshint.json

"""


simple_ini = """
[tools]
linters = pep8
"""

bad_ini = """
[tools]
linters = not there, bogus
"""


class TestTools(TestCase):
    """Test the tools."""

    def test_factory_raises_error_on_bad_linter(self):
        gh = Mock(spec=github3.GitHub)
        config = ReviewConfig()
        config.load_ini(bad_ini)
        self.assertRaises(ImportError, tools.factory, config, Review(gh, None, config), '')

    def test_factory_generates_tools(self):
        gh = Mock(spec=github3.GitHub)
        config = build_review_config(sample_ini)
        linters = tools.factory(config, Review(gh, None, config), '')
        self.assertEqual(2, len(linters))
        assert isinstance(linters[0], pep8.Pep8)
        assert isinstance(linters[1], jshint.Jshint)

    def test_tool_constructor__config(self):
        problems = Problems()
        config = {'good': 'value'}
        tool = tools.Tool(problems, config)
        self.assertEqual(tool.options, config)

        tool = tools.Tool(problems, 'derp')
        self.assertEqual(tool.options, {})

        tool = tools.Tool(problems, 2)
        self.assertEqual(tool.options, {})

        tool = tools.Tool(problems, None)
        self.assertEqual(tool.options, {})

    def test_tool_apply_base__no_base(self):
        problems = Problems()
        tool = tools.Tool(problems, {})

        result = tool.apply_base('comments_current.json')
        self.assertEqual(result, 'comments_current.json')

    def test_tool_apply_base__with_base(self):
        problems = Problems()
        tool = tools.Tool(problems, {}, fixtures_path)

        result = tool.apply_base('comments_current.json')
        self.assertEqual(result, fixtures_path + '/comments_current.json')

        result = tool.apply_base('./comments_current.json')
        self.assertEqual(result, fixtures_path + '/comments_current.json')

        result = tool.apply_base('eslint/config.json')
        self.assertEqual(result, fixtures_path + '/eslint/config.json')

        result = tool.apply_base('./eslint/config.json')
        self.assertEqual(result, fixtures_path + '/eslint/config.json')

        result = tool.apply_base('../fixtures/eslint/config.json')
        self.assertEqual(result, fixtures_path + '/eslint/config.json')

    def test_tool_apply_base__with_base_no_traversal(self):
        problems = Problems()
        tool = tools.Tool(problems, {}, fixtures_path)

        result = tool.apply_base('../../../comments_current.json')
        self.assertEqual(result, 'comments_current.json')

    @pytest.mark.requires_linters
    def test_run(self):
        config = build_review_config(simple_ini)
        problems = Problems()
        files = ['./tests/fixtures/pep8/has_errors.py']
        tool_list = tools.factory(config, problems, root_dir)
        tools.run(tool_list, files, [])
        self.assertEqual(6, len(problems))

    @pytest.mark.requires_linters
    def test_run__filter_files(self):
        config = build_review_config(simple_ini)
        problems = Problems()
        files = [
            './tests/fixtures/pep8/has_errors.py',
            './tests/fixtures/phpcs/has_errors.php'
        ]
        tool_list = tools.factory(config, problems, root_dir)
        tools.run(tool_list, files, [])
        self.assertEqual(6, len(problems))

    def test_python_image(self):
        self.assertEqual('python2', tools.python_image(False))
        self.assertEqual('python2', tools.python_image(''))
        self.assertEqual('python2', tools.python_image('derp'))
        self.assertEqual('python2', tools.python_image({}))
        self.assertEqual('python2', tools.python_image([]))
        self.assertEqual('python2', tools.python_image({'python': 2}))
        self.assertEqual('python2', tools.python_image({'python': '2'}))
        self.assertEqual('python3', tools.python_image({'python': '3'}))
        self.assertEqual('python3', tools.python_image({'python': 3}))

    def test_process_checkstyle(self):
        problems = Problems()
        xml = """
    <checkstyle>
      <file name="things.py">
        <error line="1" message="Not good" />
        <error line="2" message="Also not good" />
      </file>
      <file name="other_things.py">
        <error line="3" message="Not good" />
      </file>
    </checkstyle>
    """
        tools.process_checkstyle(problems, xml, lambda x: x)
        self.assertEqual(3, len(problems))

        things = problems.all('things.py')
        self.assertEqual(2, len(things))
        self.assertEqual(1, things[0].line)
        self.assertEqual('Not good', things[0].body)

    def test_process_checkstyle__comma_lines(self):
        problems = Problems()
        xml = """
    <checkstyle>
      <file name="other_things.py">
        <error line="3,4,5" message="Not good" />
      </file>
    </checkstyle>
    """
        tools.process_checkstyle(problems, xml, lambda x: x)
        self.assertEqual(3, len(problems))

        things = problems.all('other_things.py')
        self.assertEqual(3, len(things))
        self.assertEqual(3, things[0].line)
        self.assertEqual('Not good', things[0].body)

        self.assertEqual(4, things[1].line)
        self.assertEqual('Not good', things[1].body)

        self.assertEqual(5, things[2].line)
        self.assertEqual('Not good', things[2].body)

    def test_process_checkstyle__non_int(self):
        problems = Problems()
        xml = """
    <checkstyle>
      <file name="other_things.py">
        <error line="undefined" message="Not good" />
      </file>
    </checkstyle>
    """
        tools.process_checkstyle(problems, xml, lambda x: x)
        self.assertEqual(0, len(problems))
