"""
test_cli.py
author: @mbiokyle29
"""
import datetime
import json
import os
import tempfile
import unittest
from pkg_resources import resource_string

import responses
from click.testing import CliRunner
from mock import Mock, patch
from pyfakefs import fake_filesystem_unittest
from testfixtures import Replace, Replacer
from testfixtures.popen import MockPopen

from onecodex import Cli

DATE_FORMAT = "%Y-%m-%d %H:%M"


class TestCli(unittest.TestCase):

    def setUp(self):

        self.runner = CliRunner()
        self.base_url = "http://localhost:5000/api/v1/"

        # set the ENV var so the cli uses the mocked endpoint
        self._old_endpoint = os.environ.get('ONE_CODEX_API_BASE')
        os.environ['ONE_CODEX_API_BASE'] = "http://localhost:5000"

        # analyses
        self.analysis_uri = "4a668ac6daf74364"
        self.analysis_link = "{}analyses/{}".format(self.base_url,
                                                    self.analysis_uri)
        self.analysis = resource_string(__name__,
                                        'data/cli/analysis.json')

        # samples
        self.sample_uri = "d5a69fe85b7a4208"
        self.sample_link = "{}samples/{}".format(self.base_url,
                                                 self.sample_uri)
        self.sample = resource_string(__name__,
                                      'data/cli/sample.json')

        # classifications
        self.classification_uri = "4a668ac6daf74364"
        self.classification_link = "{}classifications/{}".format(
            self.base_url, self.classification_uri)

        self.classification = resource_string(__name__,
                                              'data/cli/classification.json')
        # TODO: add markerpanels?

        # expected messages
        self.help_message = "One Codex v1 API command line interface"
        self.version_message = "onecodex, version"

    def tearDown(self):
        if self._old_endpoint is not None:
            os.environ['ONE_CODEX_API_BASE'] = self._old_endpoint

    def test_help_long(self):

        result = self.runner.invoke(Cli, ["--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(self.help_message in result.output)

    def test_help_short(self):

        result = self.runner.invoke(Cli, ["-h"])
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(self.help_message in result.output)

    def test_empty_helps(self):

        result = self.runner.invoke(Cli)
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(self.help_message in result.output)

    def test_version(self):

        result = self.runner.invoke(Cli, ["--version"])
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(self.version_message in result.output)

    @responses.activate
    def test_analyses_help(self):

        self.schema_url = "http://localhost:5000/api/v1/schema"
        self.schema_file = resource_string(__name__, 'data/schema.json')
        responses.add(responses.GET, self.schema_url,
                      json=json.loads(self.schema_file))
        responses.add(responses.GET, self.analysis_link,
                      json=json.loads(self.analysis))
        responses.add(responses.GET, self.sample_link,
                      json=json.loads(self.sample))

        help_result = self.runner.invoke(Cli, ["analyses", "--help"])
        analysis_desc = "Retrieve performed analyses"
        self.assertEqual(help_result.exit_code, 0)
        self.assertTrue(analysis_desc in help_result.output)

    @responses.activate
    def test_analysis(self):
        self.schema_url = "http://localhost:5000/api/v1/schema"
        self.schema_file = resource_string(__name__, 'data/schema.json')
        responses.add(responses.GET, self.schema_url,
                      json=json.loads(self.schema_file))
        responses.add(responses.GET, self.analysis_link,
                      json=json.loads(self.analysis))
        responses.add(responses.GET, self.sample_link,
                      json=json.loads(self.sample))

        help_result = self.runner.invoke(Cli, ["analyses", "--help"])
        analysis_desc = "Retrieve performed analyses"
        self.assertEqual(help_result.exit_code, 0)
        self.assertTrue(analysis_desc in help_result.output)

        fetch_result = self.runner.invoke(Cli, ["analyses", self.analysis_uri])
        self.assertEqual(fetch_result.exit_code, 0)
        self.assertTrue(
            "\"$uri\": \"/api/v1/analyses/{}\"".format(self.analysis_uri) in fetch_result.output)  # noqa

    @responses.activate
    def test_sample(self):
        self.schema_url = "http://localhost:5000/api/v1/schema"
        self.schema_file = resource_string(__name__, 'data/schema.json')
        responses.add(responses.GET, self.schema_url,
                      json=json.loads(self.schema_file))
        responses.add(responses.GET, self.sample_link,
                      json=json.loads(self.sample))

        help_result = self.runner.invoke(Cli, ["samples", "--help"])
        sample_desc = "Retrieve uploaded samples"
        self.assertEqual(help_result.exit_code, 0)
        self.assertTrue(sample_desc in help_result.output)

        fetch_result = self.runner.invoke(Cli, ["samples", self.sample_uri])
        self.assertEqual(fetch_result.exit_code, 0)
        self.assertTrue(
            "\"$uri\": \"/api/v1/samples/{}\"".format(self.sample_uri) in fetch_result.output)  # noqa

    @responses.activate
    def test_classification(self):
        self.schema_url = "http://localhost:5000/api/v1/schema"
        self.schema_file = resource_string(__name__, 'data/schema.json')
        responses.add(responses.GET, self.schema_url,
                      json=json.loads(self.schema_file))
        responses.add(responses.GET, self.classification_link,
                      json=json.loads(self.classification))
        responses.add(responses.GET, self.sample_link,
                      json=json.loads(self.sample))

        help_result = self.runner.invoke(Cli, ["classifications", "--help"])
        class_desc = "Retrieve performed metagenomic classifications"
        self.assertEqual(help_result.exit_code, 0)
        self.assertTrue(class_desc in help_result.output)

        for option in ["--raw", "--table"]:
            self.assertTrue(option in help_result.output)

        fetch_result = self.runner.invoke(
            Cli, ["classifications", self.classification_uri])

        self.assertEqual(fetch_result.exit_code, 0)
        self.assertTrue(
            "\"$uri\": \"/api/v1/classifications/{}\"".format(self.classification_uri) in fetch_result.output)  # noqa


class TestCliLogin(fake_filesystem_unittest.TestCase):

    def setUp(self):
        super(TestCliLogin, self).setUp()
        self.runner = CliRunner()
        self.base_url = "http://localhost:5000/api/v1/"
        self.email = "kyle@onecodex.com"
        self.password = "password!"
        self.api_key = "123yuixha87yd87q3123uiqhsd8q2738"
        self.login_input = self.email + "\n" + self.password + "\n"

        # set the ENV var so the cli uses the mocked endpoint
        self._old_endpoint = os.environ.get('ONE_CODEX_API_BASE')
        os.environ['ONE_CODEX_API_BASE'] = "http://localhost:5000"

        self.setUpPyfakefs()
        os.makedirs(os.path.expanduser("~/"))

    def tearDown(self):
        super(TestCliLogin, self).tearDownClass()
        if self._old_endpoint is not None:
            os.environ['ONE_CODEX_API_BASE'] = self._old_endpoint

    # patch function
    def mock_fetch_api_key(self, username, password, server_url):
        return self.api_key

    def make_creds_file(self):
        now = datetime.datetime.now().strftime(DATE_FORMAT)
        fake_creds = {'api_key': self.api_key, 'saved_at': now, 'updated_at': None}
        path = os.path.expanduser("~/.onecodex")
        self.fs.CreateFile(path, contents=json.dumps(fake_creds))

    def test_api_login(self):

        successful_login_msg = "Your ~/.onecodex credentials file successfully created."

        with Replace('onecodex.auth.fetch_api_key_from_uname', self.mock_fetch_api_key):
            result = self.runner.invoke(Cli, ["login"], input=self.login_input)
            self.assertEqual(result.exit_code, 0)
            self.assertTrue(successful_login_msg in result.output)

    def test_creds_file_exists(self):

        self.make_creds_file()
        expected_message = "Credentials file already exists"

        result = self.runner.invoke(Cli, ["login"])
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(expected_message in result.output)

    def test_creds_file_corrupted(self):

        path = os.path.expanduser("~/.onecodex")
        self.fs.CreateFile(path, contents="aslkdjaslkd\nkasjdlkas\nasdkjaslkd908&S&&^")
        expected_message = "Your ~/.onecodex credentials file appears to be corrupted."

        result = self.runner.invoke(Cli, ["login"])
        self.assertEqual(result.exit_code, 1)
        self.assertTrue(expected_message in result.output)

    def test_logout_creds_exists(self):

        self.make_creds_file()
        expected_message = "Successfully removed One Codex credentials."
        path = os.path.expanduser("~/.onecodex")

        result = self.runner.invoke(Cli, ["logout"])
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(expected_message in result.output)
        self.assertFalse(os.path.exists(path))

    def test_logout_creds_dne(self):

        expected_message = "No One Codex API keys found."
        result = self.runner.invoke(Cli, ["logout"])
        self.assertEqual(result.exit_code, 1)
        self.assertTrue(expected_message in result.output)


class TestCliUpload(unittest.TestCase):

    def setUp(self):

        self.runner = CliRunner()
        self.base_url = "http://localhost:5000/api/v1/"
        self.api_key = "123yuixha87yd87q3123uiqhsd8q2738"

        # set the ENV var so the cli uses the mocked endpoint
        self._old_endpoint = os.environ.get('ONE_CODEX_API_BASE')
        os.environ['ONE_CODEX_API_BASE'] = "http://localhost:5000"

        self.presign_upload_base = "samples/presign_upload"
        self.presign_upload_url = self.base_url + self.presign_upload_base

        self.callback_base = "/api/confirm_upload"
        self.callback_url = self.base_url.replace("/api/v1/", self.callback_base)

        self.s3_signing_base = "/s3_sign"
        self.s3_signing_url = self.base_url.replace("/api/v1/", self.s3_signing_base)

        self.s3_url = "https://aws.com/"

        self.presign_json = json.dumps({"callback_url": self.callback_base,
                                        "signing_url": self.s3_signing_base,
                                        "url": self.s3_url})

        self.signing_json = json.dumps({'AWSAccessKeyId': 'AKIAI36HUSHZTL3A7ORQ',
                                        'success_action_status': 201,
                                        'acl': 'private',
                                        'key': 'asd/file_ab6276c673814123/${filename}',
                                        'signature': 'asdjsa',
                                        'policy': '123123123',
                                        'x-amz-server-side-encryption': 'AES256'})

    def tearDown(self):
        if self._old_endpoint is not None:
            os.environ['ONE_CODEX_API_BASE'] = self._old_endpoint

    def write_seq_data(self, file):
        with open(file, "w") as fh:
            fh.write(">TEST_FASTA\n")
            fh.write("ATGCATGCATGCTAGCTGATCGATGGGTAGCATGCTA\n")
            fh.write("ATGCATGCATGCTAGCTGATCGATGGGTAGCATGCTA\n")
            fh.write("ATGCATGCATGCTAGCTGATCGATGGGTAGCATGCTA\n")
            fh.write("ATGCATGCATGCTAGCTGATCGATGGGTAGCATGCTA\n")

    @responses.activate
    def test_upload_one_file_no_threads(self):

        self.schema_url = "http://localhost:5000/api/v1/schema"
        self.schema_file = resource_string(__name__, 'data/schema.json')
        responses.add(responses.GET, self.schema_url,
                      json=json.loads(self.schema_file))

        def upload_callback(request):
            return (201, {'location': 'on-aws'}, json.dumps({}))

        responses.add(responses.GET, self.presign_upload_url,
                      body=self.presign_json)

        responses.add(responses.POST, self.s3_signing_url,
                      body=self.signing_json)

        responses.add_callback(
            responses.POST, self.s3_url,
            callback=upload_callback,
            content_type='multipart/form-data'
        )

        responses.add(responses.POST, self.callback_url,
                      status=200, content_type='application/json')

        os_handle, filename = tempfile.mkstemp(suffix=".fa")
        self.write_seq_data(filename)

        result = self.runner.invoke(Cli, ["--api-key", self.api_key, "upload", "--no-threads", filename])
        self.assertEqual(result.exit_code, 0)
        os.remove(filename)

    @responses.activate
    def test_upload_one_file_threads(self):
        self.schema_url = "http://localhost:5000/api/v1/schema"
        self.schema_file = resource_string(__name__, 'data/schema.json')
        responses.add(responses.GET, self.schema_url,
                      json=json.loads(self.schema_file))

        def upload_callback(request):
            return (201, {'location': 'on-aws'}, json.dumps({}))

        responses.add(responses.GET, self.presign_upload_url,
                      body=self.presign_json)

        responses.add(responses.POST, self.s3_signing_url,
                      body=self.signing_json)

        responses.add_callback(
            responses.POST, self.s3_url,
            callback=upload_callback,
            content_type='multipart/form-data'
        )

        responses.add(responses.POST, self.callback_url,
                      status=200, content_type='application/json')

        os_handle, filename = tempfile.mkstemp(suffix=".fa")
        self.write_seq_data(filename)

        result = self.runner.invoke(Cli, ["--api-key", self.api_key, "upload", filename])
        self.assertEqual(result.exit_code, 0)
        os.remove(filename)

    @responses.activate
    def test_upload_multiple_files_serial(self):
        self.schema_url = "http://localhost:5000/api/v1/schema"
        self.schema_file = resource_string(__name__, 'data/schema.json')
        responses.add(responses.GET, self.schema_url,
                      json=json.loads(self.schema_file))

        def upload_callback(request):
            return (201, {'location': 'on-aws'}, json.dumps({}))

        responses.add(responses.GET, self.presign_upload_url,
                      body=self.presign_json)

        responses.add(responses.POST, self.s3_signing_url,
                      body=self.signing_json)

        responses.add_callback(
            responses.POST, self.s3_url,
            callback=upload_callback,
            content_type='multipart/form-data'
        )

        responses.add(responses.POST, self.callback_url,
                      status=200, content_type='application/json')

        os_one, file_one = tempfile.mkstemp(suffix=".fa")
        self.write_seq_data(file_one)

        os_two, file_two = tempfile.mkstemp(suffix=".fa")
        self.write_seq_data(file_two)

        result = self.runner.invoke(Cli, ["--api-key", self.api_key, "upload", "--no-threads", file_one, file_two])
        self.assertEqual(result.exit_code, 0)
        self.assertTrue("1 thread(s)" in result.output)
        self.assertTrue(file_one in result.output)
        self.assertTrue(file_two in result.output)
        os.remove(file_one)
        os.remove(file_two)

    @responses.activate
    def test_upload_multiple_files_threads(self):
        self.schema_url = "http://localhost:5000/api/v1/schema"
        self.schema_file = resource_string(__name__, 'data/schema.json')
        responses.add(responses.GET, self.schema_url,
                      json=json.loads(self.schema_file))

        def upload_callback(request):
            return (201, {'location': 'on-aws'}, json.dumps({}))

        responses.add(responses.GET, self.presign_upload_url,
                      body=self.presign_json)

        responses.add(responses.POST, self.s3_signing_url,
                      body=self.signing_json)

        responses.add_callback(
            responses.POST, self.s3_url,
            callback=upload_callback,
            content_type='multipart/form-data'
        )

        responses.add(responses.POST, self.callback_url,
                      status=200, content_type='application/json')

        os_one, file_one = tempfile.mkstemp(suffix=".fa")
        self.write_seq_data(file_one)

        os_two, file_two = tempfile.mkstemp(suffix=".fa")
        self.write_seq_data(file_two)

        result = self.runner.invoke(Cli, ["--api-key", self.api_key, "upload", "--max-threads", 5, file_one, file_two])
        self.assertEqual(result.exit_code, 0)
        self.assertTrue("up to 5 thread(s)" in result.output)
        self.assertTrue(file_one in result.output)
        self.assertTrue(file_two in result.output)
        os.remove(file_one)
        os.remove(file_two)

    @responses.activate
    def test_empty_file(self):
        self.schema_url = "http://localhost:5000/api/v1/schema"
        self.schema_file = resource_string(__name__, 'data/schema.json')
        responses.add(responses.GET, self.schema_url,
                      json=json.loads(self.schema_file))

        def upload_callback(request):
            return (201, {'location': 'on-aws'}, json.dumps({}))

        responses.add(responses.GET, self.presign_upload_url,
                      body=self.presign_json)

        responses.add(responses.POST, self.s3_signing_url,
                      body=self.signing_json)

        responses.add_callback(
            responses.POST, self.s3_url,
            callback=upload_callback,
            content_type='multipart/form-data'
        )

        responses.add(responses.POST, self.callback_url,
                      status=200, content_type='application/json')

        os_one, file_one = tempfile.mkstemp(suffix=".fa")
        result = self.runner.invoke(Cli, ["--api-key", self.api_key, "--verbose", "upload", file_one])
        self.assertNotEqual(result.exit_code, 0)


class TestCliBigUpload(unittest.TestCase):

    def setUp(self):

        self.runner = CliRunner()
        self.base_url = "http://localhost:5000/api/v1/"
        self.api_key = "123yuixha87yd87q3123uiqhsd8q2738"

        # set the ENV var so the cli uses the mocked endpoint
        self._old_endpoint = os.environ.get('ONE_CODEX_API_BASE')
        os.environ['ONE_CODEX_API_BASE'] = "http://localhost:5000"

        self.presign_upload_base = "samples/presign_upload"
        self.presign_upload_url = self.base_url + self.presign_upload_base

        self.callback_base = "/api/confirm_upload"
        self.callback_url = self.base_url.replace("/api/v1/", self.callback_base)

        self.s3_signing_base = "/s3_sign"
        self.s3_signing_url = self.base_url.replace("/api/v1/", self.s3_signing_base)

        self.s3_url = "https://aws.com/"

        self.presign_json = json.dumps({"callback_url": self.callback_base,
                                        "signing_url": self.s3_signing_base,
                                        "url": self.s3_url})

        self.signing_json = json.dumps({'AWSAccessKeyId': 'AKIAI36HUSHZTL3A7ORQ',
                                        'success_action_status': 201,
                                        'acl': 'private',
                                        'key': 'asd/file_ab6276c673814123/${filename}',
                                        'signature': 'asdjsa',
                                        'policy': '123123123',
                                        'x-amz-server-side-encryption': 'AES256'})

        # mock subprocess call
        dotted_path = "subprocess.Popen"
        self.Popen = MockPopen()
        self.r = Replacer()
        self.r.replace(dotted_path, self.Popen)
        self.addCleanup(self.r.restore)

        self.multipart_callback_base = "/api/import_file_from_s3"
        self.multipart_callback_url = self.base_url.replace("/api/v1/",
                                                            self.multipart_callback_base)

        self.multipart_init_base = "samples/init_multipart_upload"
        self.multipart_upload_init_url = self.base_url + self.multipart_init_base
        self.file_id = "1234"
        self.bucket = "onecodex-multipart-uploads-encrypted"
        self.aws_id = "28ejashdas"
        self.aws_key = "asdasd/1233/+/9"
        self.multipart_init_json = json.dumps({
            "callback_url": self.multipart_callback_base,
            "file_id": self.file_id,
            "s3_bucket": self.bucket,
            "upload_aws_access_key_id": self.aws_id,
            "upload_aws_secret_access_key": self.aws_key
        })

    @responses.activate
    def test_upload_s3(self):
        self.schema_url = "http://localhost:5000/api/v1/schema"
        self.schema_file = resource_string(__name__, 'data/schema.json')
        responses.add(responses.GET, self.schema_url,
                      json=json.loads(self.schema_file))
        responses.add(responses.GET, self.multipart_upload_init_url,
                      body=self.multipart_init_json)

        responses.add(responses.POST, self.multipart_callback_url,
                      status=200)

        os_handle, big_file = tempfile.mkstemp(suffix=".fa")
        bucket = "s3://{}/{}".format(self.bucket, self.file_id)
        cmd = "AWS_ACCESS_KEY_ID={} AWS_SECRET_ACCESS_KEY={} aws s3 cp {} {} --sse".format(self.aws_id,
                                                                                           self.aws_key,
                                                                                           big_file,
                                                                                           bucket)

        # mocking cli and os.path
        mock = Mock()

        def get_size(file_path):
            return 5 * 1000 * 1000 * 1000 + 1

        expected_strings = [
            "Starting large (>5GB) file upload. Please be patient while the file transfers...",
            "Successfully uploaded: {}".format(big_file)
        ]

        with patch.dict('sys.modules', {'awscli': mock}):
            with Replace('os.path.getsize', get_size):
                self.Popen.set_command(cmd)
                result = self.runner.invoke(Cli, ["--api-key", self.api_key, "upload", big_file])
                self.assertEqual(result.exit_code, 0)
                for string in expected_strings:
                    self.assertTrue(string in result.output)
