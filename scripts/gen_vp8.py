#!/usr/bin/env python3

# Fluster - testing framework for decoders conformance
# Copyright (C) 2020, Collabora, Ltd.
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

import argparse
import github
import os
import sys
import urllib.request
import multiprocessing

# pylint: disable=wrong-import-position
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from fluster import utils
from fluster.codec import Codec, PixelFormat
from fluster.test_suite import TestSuite, TestVector
# pylint: enable=wrong-import-position


API_URL = 'https://api.github.com'
VP8_REPO = 'webmproject/vp8-test-vectors'
GITHUB_RAW_BASE_URL = 'https://github.com/webmproject/vp8-test-vectors/raw/master/'
BITSTREAM_EXT = '.ivf'
MD5_EXT = '.md5'

class VP8Generator:
    '''Generates a test suite from the Webm conformance bitstreams'''

    def __init__(self, name: str, suite_name: str, codec: Codec, description: str, github_mirror: str):
        self.name = name
        self.suite_name = suite_name
        self.codec = codec
        self.description = description
        self.github_mirror = github_mirror

    def generate(self, download, jobs):
        '''Generates the test suite and saves it to a file'''
        output_filepath = os.path.join(self.suite_name + '.json')
        test_suite = TestSuite(output_filepath, 'resources',
                               self.suite_name, self.codec, self.description, dict())
        g = github.MainClass.Github(base_url=API_URL)
        repo = g.get_repo(self.github_mirror)
        contents = repo.get_contents("")
        for content_file in contents:
            if not self.is_test_vector(content_file.name):
                continue
            file_url = content_file.name
            url = GITHUB_RAW_BASE_URL + file_url
            name = os.path.splitext(file_url)[0]
            test_vector = TestVector(
                name, url, '', file_url, PixelFormat.yuv420p, '')
            test_suite.test_vectors[name] = test_vector

        if download:
            test_suite.download(jobs=jobs, out_dir=test_suite.resources_dir, verify=False,
                                extract_all=True, keep_file=True)

        for test_vector in test_suite.test_vectors.values():
            dest_dir = os.path.join(
                test_suite.resources_dir, test_suite.name, test_vector.name)
            dest_path = os.path.join(
                dest_dir, os.path.basename(test_vector.source))
            test_vector.source_checksum = utils.file_checksum(dest_path)

        test_suite.to_json_file(output_filepath)
        print('Generate new test suite: ' + test_suite.name + '.json')

    def is_test_vector(self, filename):
        if filename.endswith(BITSTREAM_EXT):
            return True
        return False

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--skip-download', help='skip extracting tarball',
                        action='store_true', default=False)
    parser.add_argument(
        '-j', '--jobs', help='number of parallel jobs to use. 2x logical cores by default',
        type=int, default=2 * multiprocessing.cpu_count())
    args = parser.parse_args()
    generator = VP8Generator('VP8', 'WebM-VP8', Codec.VP8,
                               'WebM VP8 Test Vector Catalogue', VP8_REPO)
    generator.generate(not args.skip_download, args.jobs)
