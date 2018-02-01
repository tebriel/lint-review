from __future__ import absolute_import
import os
import logging
from lintreview.tools import Tool, run_command, process_quickfix
from lintreview.utils import in_path

log = logging.getLogger(__name__)


class Flake8(Tool):

    name = 'flake8'

    # see: http://flake8.readthedocs.org/en/latest/config.html
    PYFLAKE_OPTIONS = [
        'config',
        'exclude',
        'filename',
        'format',
        'ignore',
        'max-complexity',
        'max-line-length',
        'select',
        'snippet',
    ]

    AUTOPEP8_OPTIONS = [
        'exclude',
        'max-line-length',
        'select',
        'ignore',
    ]

    def check_dependencies(self):
        """
        See if flake8 is on the PATH
        """
        return in_path('flake8')

    def match_file(self, filename):
        base = os.path.basename(filename)
        name, ext = os.path.splitext(base)
        return ext == '.py'

    def process_files(self, files):
        """
        Run code checks with flake8.
        Only a single process is made for all files
        to save resources.
        """
        log.debug('Processing %s files with %s', len(files), self.name)
        command = self.make_command(files)
        output = run_command(command, split=True, ignore_error=True)
        if not output:
            log.debug('No flake8 errors found.')
            return False

        process_quickfix(self.problems, output, lambda name: name)

    def make_command(self, files):
        command = ['flake8', '--isolated']
        for option in self.options:
            if option in self.PYFLAKE_OPTIONS:
                command.extend([
                    '--%s' % option,
                    self.options.get(option)
                ])

        command += files
        return command

    def has_fixer(self):
        """
        flake8 has a fixer that can be enabled through configuration.
        """
        return bool(self.options.get('fixer', False))

    def process_fixer(self, files):
        """Run autopep8, as flake8 has no fixer mode.
        """
        command = self.create_fixer_command(files)
        run_command(
            command,
            ignore_error=True,
            include_errors=False)

    def create_fixer_command(self, files):
        command = [
            'autopep8',
            '--in-place',
            '--ignore-local-config',
            '--pep8-passes', '5'
        ]
        for option in self.options:
            if option in self.AUTOPEP8_OPTIONS:
                command.extend([
                    '--%s' % option,
                    self.options.get(option)
                ])
        if 'config' in self.options:
            command.extend(['--global-config', self.options.get('config')])
        command += files
        return command
