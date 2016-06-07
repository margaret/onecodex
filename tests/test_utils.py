"""
test_api.py
author: @mbiokyle29
"""
import unittest
from functools import partial

from click import BadParameter

from onecodex.utils import (
    check_for_allowed_file,
    valid_api_key
)


class TestUtils(unittest.TestCase):

    def test_check_allowed_file(self):

        # bad ones
        with self.assertRaises(SystemExit):
            check_for_allowed_file("file.bam")
            check_for_allowed_file("file")

        # good ones
        check_for_allowed_file("file.fastq")
        check_for_allowed_file("file.fastq.gz")

    def test_is_valid_api_key(self):

        empty_api = ""
        short_api = "123"
        long_api = "123abc123abc123abc123abc123abc123abc123abc123abc123abc"
        good_api = "123abc123abc123abc123abc123abc32"

        # its a click callback so it expects some other params
        valid_api_key_p = partial(valid_api_key, None, None)

        for faulty_api in [empty_api, short_api, long_api]:
            with self.assertRaises(BadParameter):
                valid_api_key_p(faulty_api)

        self.assertEqual(good_api, valid_api_key_p(good_api))
