# Fluster - testing framework for decoders conformance
# Copyright (C) 2020, Fluendo, S.A.
#  Author: Pablo Marcos Oltra <pmarcos@fluendo.com>, Fluendo, S.A.
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Library General Public
# License as published by the Free Software Foundation; either
# version 2 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Library General Public License for more details.
#
# You should have received a copy of the GNU Library General Public
# License along with this library; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place - Suite 330,
# Boston, MA 02111-1307, USA.

import os
import os.path
from functools import lru_cache
import sys

# Import decoders that will auto-register
# pylint: disable=wildcard-import, unused-wildcard-import
from fluster.decoders import *
# pylint: enable=wildcard-import, unused-wildcard-import

from fluster.test_suite import TestSuite
from fluster.test_suite import Context as TestSuiteContext
from fluster.decoder import DECODERS

# pylint: disable=broad-except


class Context:
    '''Context for run and reference command'''
    # pylint: disable=too-few-public-methods, too-many-instance-attributes

    def __init__(self, jobs: int, timeout: int, test_suites: list = None, decoders: list = None,
                 test_vectors: list = None, failfast: bool = False, quiet: bool = False,
                 reference: bool = False, summary: bool = False, keep_files: bool = False):
        self.jobs = jobs
        self.timeout = timeout
        self.test_suites = test_suites
        self.decoders = decoders
        self.test_vectors = test_vectors
        self.failfast = failfast
        self.quiet = quiet
        self.reference = reference
        self.summary = summary
        self.keep_files = keep_files

    def to_test_suite_context(self, decoder, results_dir, test_vectors):
        '''Create a TestSuite's Context from this'''
        ts_context = TestSuiteContext(jobs=self.jobs, decoder=decoder, timeout=self.timeout, failfast=self.failfast,
                                      quiet=self.quiet, results_dir=results_dir, reference=self.reference,
                                      test_vectors=test_vectors, keep_files=self.keep_files)
        return ts_context


class Fluster:
    '''Main class for fluster'''

    def __init__(self, test_suites_dir: str, decoders_dir: str, resources_dir: str,
                 results_dir: str, verbose: bool = False):
        self.test_suites_dir = test_suites_dir
        self.decoders_dir = decoders_dir
        self.resources_dir = resources_dir
        self.results_dir = results_dir
        self.verbose = verbose
        self.test_suites = []
        self.decoders = DECODERS

    @lru_cache(maxsize=None)
    def _load_test_suites(self):
        for root, _, files in os.walk(self.test_suites_dir):
            for file in files:
                if os.path.splitext(file)[1] == '.json':
                    if self.verbose:
                        print(f'Test suite found: {file}')
                    try:
                        test_suite = TestSuite.from_json_file(
                            os.path.join(root, file), self.resources_dir)
                        self.test_suites.append(test_suite)
                    except Exception as ex:
                        print(f'Error loading test suite {file}: {ex}')

    def list_decoders(self, check: bool = False):
        '''List all the available decoders'''
        print('\nList of available decoders:\n')
        decoders_dict = {}
        for dec in self.decoders:
            if dec.codec not in decoders_dict:
                decoders_dict[dec.codec] = []
            decoders_dict[dec.codec].append(dec)

        for codec in decoders_dict:
            print(f'{codec}'.split('.')[1])
            for decoder in decoders_dict[codec]:
                string = f'{decoder}'
                if check:
                    string += ' ✔️' if decoder.check() else ' ❌'
                print(string)

    def list_test_suites(self, show_test_vectors: bool = False, test_suites: list = None):
        '''List all test suites'''
        self._load_test_suites()
        print('\nList of available test suites:')
        if test_suites:
            test_suites = [x.lower() for x in test_suites]
        for test_suite in self.test_suites:
            if test_suites:
                if test_suite.name.lower() not in test_suites:
                    continue
            print(test_suite)
            if show_test_vectors:
                for test_vector in test_suite.test_vectors.values():
                    print(test_vector)

    def _get_run_param(self, in_list: list, check_list: list, name: str):
        if in_list:
            run = [x for x in check_list if x.name.lower() in in_list]
            if not run:
                raise Exception(
                    f'No {name} found matching {in_list}')
        else:
            run = check_list
        return run

    def _normalize_context(self, ctx: Context):
        # Convert all test suites and decoders to lowercase to make the filter greedy
        if ctx.test_suites:
            ctx.test_suites = [x.lower() for x in ctx.test_suites]
        if ctx.decoders:
            ctx.decoders = [x.lower() for x in ctx.decoders]
        if ctx.test_vectors:
            ctx.test_vectors = [x.lower() for x in ctx.test_vectors]
        ctx.test_suites = self._get_run_param(
            ctx.test_suites, self.test_suites, 'test suite')
        ctx.decoders = self._get_run_param(
            ctx.decoders, self.decoders, 'decoders')

    def run_test_suites(self, ctx: Context):
        '''Run a group of test suites'''
        self._load_test_suites()
        self._normalize_context(ctx)

        if ctx.reference and (not ctx.decoders or len(ctx.decoders) > 1):
            dec_names = [dec.name for dec in ctx.decoders]
            raise Exception(
                f'Only one decoder can be the reference. Given: {", ".join(dec_names)}')

        if ctx.reference:
            print('Reference mode')

        error = False
        for ctx.test_suite in ctx.test_suites:
            results = []
            for decoder in ctx.decoders:
                if decoder.codec != ctx.test_suite.codec:
                    continue
                test_suite_res = ctx.test_suite.run(
                    ctx.to_test_suite_context(decoder, self.results_dir, ctx.test_vectors))

                if test_suite_res:
                    results.append((decoder, test_suite_res))
                    success = True
                    for test_vector in test_suite_res.test_vectors.values():
                        if test_vector.errors:
                            success = False
                            break

                    if not success:
                        if ctx.failfast:
                            sys.exit(1)
                        error = True

            if ctx.summary and results:
                self._generate_summary(results)
        if error:
            sys.exit(1)

    def _generate_summary(self, results: tuple):
        test_suite_name = results[0][1].name
        decoder_names = [decoder.name for decoder, _ in results]
        test_suites = [res[1] for res in results]
        print(
            f'Generating summary for test suite {test_suite_name} and decoders {", ".join(decoder_names)}:\n')
        output = '|Test|'
        for decoder, _ in results:
            output += f'{decoder.name}|'
        output += f'\n|-|{"-|" * len(results)}'
        for test_vector in results[0][1].test_vectors.values():
            output += f'\n|{test_vector.name}|'
            for test_suite in test_suites:
                tvector = test_suite.test_vectors[test_vector.name]
                output += '✔️|' if not tvector.errors else '❌|'
        output += '\n|TOTAL|'
        for test_suite in test_suites:
            output += f'{test_suite.test_vectors_success}/{len(test_suite.test_vectors)}|'
        print(output)

    def download_test_suites(self, test_suites: list, jobs: int, keep_file: bool):
        '''Download a group of test suites'''
        self._load_test_suites()
        if not test_suites:
            test_suites = self.test_suites
        else:
            test_suites = [
                t for t in self.test_suites if t.name in test_suites]
        for test_suite in test_suites:
            test_suite.download(jobs, self.resources_dir,
                                verify=True, keep_file=keep_file)
