#!/usr/bin/env python3

import argparse
import fnmatch
import logging
import os
import string
import subprocess
import sys

import yaml

# Application exit codes
#
# These are taken from 'posix' which is missing on Windows though, but we want
# to have the same exit codes for both platforms as the target is MSYS2 anyway.
EX_CANTCREAT = 73
EX_CONFIG = 78
EX_DATAERR = 65
EX_IOERR = 74
EX_NOHOST = 68
EX_NOINPUT = 66
EX_NOPERM = 77
EX_NOUSER = 67
EX_OK = 0
EX_OSERR = 71
EX_OSFILE = 72
EX_PROTOCOL = 76
EX_SOFTWARE = 70
EX_TEMPFAIL = 75
EX_UNAVAILABLE = 69
EX_USAGE = 64


def is_project(dirs, files):
    """Tests if a directory containing the given directories and files is a Maven project."""
    return 'pom.xml' in files


def unix_path(path):
    """Converts a path to Unix format with slashes."""
    absolute = os.path.isabs(path)
    if os.pathsep != '/':
        return '/'.join(path.split(os.sep))
    if not absolute:
        return './' + path


def parse_gav(gav, defaults=(None, None, None)):
    """Parses the given GAV as a tuple.

    gav
        the GAV to parse. It must be a string with two colons separating the
        GAV parts.
    defaults
        a triple of default coordinates to return if a part from the input is
        missing

    Returns:
        a triple with the parsed GAV
    """
    parts = gav.split(':')
    if len(parts) != 3:
        raise ValueError(f"Not a valid GAV pattern: {gav}")

    for index, value in enumerate(parts):
        if len(value) == 0:
            parts[index] = defaults[index]

    return tuple(parts)


def output(*args, **kwargs):
    """Prints on the standard output and flushes the output."""
    print(*args, **kwargs, flush=True)


class GlobFilter:
    """Glob-based filter that composes of include and exclude pattern sets."""

    def __init__(self, include=None, exclude=None):
        """Creates a new instance.

        include
            the iterable of glob patterns some of which a tested value must
            match
        exclude
            the iterable of glob patterns none of which a tested value may not
            match
        """
        self.include = None if include is None else tuple(include)
        self.exclude = None if exclude is None else tuple(exclude)

    def __repr__(self):
        return f'GlobFilter(include={repr(self.include)}, exclude={repr(self.exclude)})'

    def __call__(self, value):
        """Tests if the value matches the filter.

        Returns
            `True` if the value matches at least one pattern from `include`
            and matches no pattern from `exlude` sets, `False` otherwise.
        """
        return GlobFilter.matches(value, self.include, True) and not GlobFilter.matches(value, self.exclude, False)

    @staticmethod
    def matches(value, glob_list, default=False):
        """Tests if the value matches patterns from the given list.

        value
            the value to test
        glob_list
            the list of patterns to match
        default
            the result for empty `glob_list`

        Returns
            `True` if `value` matches at least on pattern from `glob_list` and
            `False` if none matches. However, if `glob_list` produces `default`
            instead.
        """
        if glob_list is None:
            return default

        for glob in glob_list:
            if fnmatch.fnmatch(value, glob):
                return True

        return False


class Main:
    """Implements the application."""

    def __init__(self, argv, logger=None):
        """Creates the application instance with the given configuration.

        argv
            the command line to parse
        logger
            the logger to use. If `None` given, `logging.getLogger()` shall be
            used instead.
        """
        self.args = self.__parse_args(argv)
        self.logger = logger if logger is not None else logging.getLogger()
        self.logger.setLevel(self.args.log)
        self.logger.debug(f"Parsed arguments: {self.args}")

    def run(self):
        """Executes the application according to the provided configuration."""
        self.logger.debug("Launching the application")

        try:
            return self.args.command()
        except Exception as e:
            logger.fatal(str(e))
            return EX_SOFTWARE

    def __command_find(self):
        self.logger.debug("Running 'find' command")
        for project in self.__find():
            output(project)

        return EX_OK

    def __command_make(self):
        self.logger.debug("Running 'make' command")
        try:
            gav = parse_gav(self.args.coordinates, ('localhost', 'build', '1.0.0-SNAPSHOT'))
        except ValueError as e:
            logger.fatal(str(e))
            return EX_USAGE

        file = self.args.output
        mode = 'w' if self.args.force else 'x'
        with open(file, mode=mode, encoding='UTF-8') as output:
            output.write(f'''<?xml version="1.0" encoding="UTF-8" ?>
<project xmlns="http://maven.apache.org/POM/4.0.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">

  <modelVersion>4.0.0</modelVersion>

  <groupId>{gav[0]}</groupId>
  <artifactId>{gav[1]}</artifactId>
  <version>{gav[2]}</version>
  <packaging>pom</packaging>
''')

            if self.args.name:
                output.write(f'''
  <name>{self.args.name}</name>
''')

            output.write('''
  <modules>
''')
            if self.args.read:
                filtering = GlobFilter(self.args.include, self.args.exclude)
                passing = lambda value : filtering(os.path.basename(value))
                source = filter(passing, sys.stdin.readlines())
            else:
                source = self.__find()

            for project in source:
                output.write(f'    <module>{project}</module>\n')

            output.write('''  </modules>
</project>
''')
        return EX_OK

    def __find(self):
        """Yields project directories."""
        warning = lambda e : self.logger.warn(e)
        passing = GlobFilter(None, self.args.prune)
        filtering = GlobFilter(self.args.include, self.args.exclude)
        root_dir = str(os.path.normpath(self.args.dir))

        for root, dirs, files in os.walk(root_dir, onerror=warning, followlinks=True):
            if not self.args.with_root and root == root_dir:
                continue

            if is_project(dirs, files) and filtering(os.path.basename(root)):
                yield unix_path(root)
                dirs.clear()
                continue

            self.__prune(dirs, passing)

    def __prune(self, dirs, passing):
        """Removes filtered names from a list of names."""
        for index, name in enumerate(dirs):
            if not passing(name):
                del dirs[index]

    def __unknown_command(self):
        """Reacts on an unknown command."""
        if self.args.command_name is None:
            self.logger.fatal("Missing command. Use --help to display the options.")
        else:
            self.logger.fatal(f"Unknown command: {self.args.command_name}")

        return EX_USAGE

    def __parse_args(self, argv):
        """Parses the arguments with `__argument_parser`."""
        return self.__argument_parser().parse_args(argv)

    def __argument_parser(self):
        """Returns the argument parser."""
        parser = argparse.ArgumentParser(allow_abbrev=False,
            description="Helps maintaining Maven project sets.",
            epilog="To display help for commands use -h or --help option as the command's option."
        )
        parser.set_defaults(command=self.__unknown_command)

        # Common options
        group = parser.add_argument_group(title="common options")
        group.add_argument('-d', '--dir',
            default='.',
            action='store',
            metavar="DIR",
            help="the directory where to search for the projects"
        )
        group.add_argument('-i', '--include',
            default=None,
            action='append',
            metavar="GLOB",
            help="the pattern for the projects to include"
        )
        group.add_argument('-l', '--log',
            default='WARN',
            metavar="LEVEL",
            help="set the logging LEVEL (default: %(default)s)"
        )
        group.add_argument('-p', '--prune',
            default=['.git', '.svn', 'bin', 'doc', 'src', 'target'],
            action='append',
            metavar="GLOB",
            help="the pattern for directory names to avoid searching in (default: %(default)s)"
        )
        group.add_argument('-x', '--exclude',
            default=None,
            action='append',
            metavar="GLOB",
            help="the pattern for the projects to exclude"
        )
        group.add_argument('-w', '--with-root',
            action='store_true',
            help="include --dir as the possible project, otherwise --dir is always filtered"
        )

        subparsers = parser.add_subparsers(title="commands", dest='command_name')

        # Command 'find'
        subparser = subparsers.add_parser('find', allow_abbrev=False,
            help="finds the projects",
            description="Finds all projects matching the specification."
        )
        subparser.set_defaults(command=self.__command_find)

        # Command 'make'
        subparser = subparsers.add_parser('make', allow_abbrev=False,
            help="makes a Maven reactor POM for all found projects",
            description="Makes a Maven reactor POM for all found projects."
        )

        group = subparser.add_mutually_exclusive_group()
        group.add_argument('-c', '--coordinates',
            default='::',
            action='store',
            metavar="GAV",
            help="the GAV coordinates of the generated POM. The coordinates uses G:A:V syntax and " \
                 "may omit a part to use a built-in default GAV part."
        )
        group.add_argument('-f', '--force',
            action='store_true',
            help="overwrite the output file if existing"
        )
        group.add_argument('-n', '--name',
            default=None,
            action='store',
            metavar="NAME",
            help="the name of the project"
        )
        group.add_argument('-o', '--output',
            default='pom.xml',
            action='store',
            metavar="FILE",
            help="the target file to store the result in"
        )
        group.add_argument('-r', '--read',
            action='store_true',
            help="read the list of repositories from STDIN instead of finding them, but apply the"  \
                 "--include and --exclude filter"
       )
        subparser.set_defaults(command=self.__command_make)

        return parser


if __name__ == '__main__':
    # Prepare the logger
    logging_handler = logging.StreamHandler(sys.stderr)
    logging_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    logger = logging.getLogger()
    logger.setLevel(logging.FATAL)
    logger.addHandler(logging_handler)
    # Run the application
    sys.exit(Main(sys.argv[1:], logger).run())
