from contextlib import contextmanager
import json
import os
from pkg_resources import resource_string
import pytest
import re
import requests
import responses

from onecodex import Api


def intercept(func, log=False, dump=None):
    """
    Used to copy API requests to make sure test data doesn't depend upon a connection to the One
    Codex server (basically like `betamax`, but for our requests/responses setup).

    For example, to dump out a log of everything that the function `test_function` requests, do the
    following:

    >>>mock_responses = {}
    >>>intercept(test_function, dump=mock_responses)
    >>>mock_json = json.dumps(mock_responses, separators=(',', ':'))

    Then you can test the function in the future by copying the output of mock_json into
    a string literal and doing:

    >>>mock_request(test_function, mock_json)
    """
    def handle_request(request):
        if log:
            print('->', request.method, request.url)

        # patch the request through (and disable mocking for this chunk)
        responses.mock.stop()
        resp = requests.get(request.url, headers=request.headers)
        text = resp.text
        headers = resp.headers
        # for some reason, responses pitches a fit about this being in the cookie
        headers['Set-Cookie'] = headers.get('Set-Cookie', '').replace(' HttpOnly;', '')
        responses.mock.start()
        data = json.dumps(json.loads(text), separators=(',', ':'))
        if log:
            print('<-', resp.status_code, data)
        if dump is not None:
            dump[request.method + ':' + request.url.split('/', 3)[-1]] = data
        return (200, headers, text)

    regex = re.compile('.*')
    with responses.mock as rsps:
        rsps.add_callback(responses.GET, regex, callback=handle_request)
        func()


@contextmanager
def mock_requests(mock_json):
    with responses.mock as rsps:
        for mock_url, mock_data in mock_json.items():
            try:
                method, url, content_type = mock_url.split(':')
            except ValueError:
                method, url = mock_url.split(':')
                content_type = 'application/json'
            if callable(mock_data):
                rsps.add_callback(method, re.compile('http://[^/]+/' + url + '(\?.*)?$'),
                                  callback=mock_data,
                                  content_type=content_type)
            else:
                rsps.add(method, re.compile('http://[^/]+/' + url + '(\?.*)?$'),
                         body=mock_data,
                         content_type=content_type)
        yield


# TODO: Consider deleting in favor of context manager as above
def mock_requests_decorator(mock_json):
    def decorator(func):
        def wrapper(*args, **kwargs):
            print(args, kwargs)
            with responses.mock as rsps:
                for mock_url, mock_data in mock_json.items():
                    try:
                        method, url, content_type = mock_url.split(':')
                    except ValueError:
                        method, url = mock_url.split(':')
                        content_type = 'application/json'
                    if callable(mock_data):
                        rsps.add_callback(method, re.compile('http://[^/]+/' + url + '(\?.*)?$'),
                                          callback=mock_data,
                                          content_type=content_type)
                    else:
                        rsps.add(method, re.compile('http://[^/]+/' + url + '(\?.*)?$'),
                                 body=mock_data,
                                 content_type=content_type)
                func(*args, **kwargs)
                assert len(responses.calls) > 0
        return wrapper
    return decorator


def rs(path):
    return resource_string(__name__, path).decode('utf-8')


# Organized by resources
# then a tuple of the path, and JSON
MOCK_DATA = {
    'schema': {
        'uri': 'GET:api/v1/schema',
        'json': json.loads(rs('data/schema.json'))
    },
    'analysis1': {
        'uri': 'GET:api/v1/analyses/4a668ac6daf74364',
        'json': json.loads(rs('data/cli/analysis.json'))
    },
    'classification1': {
        'uri': 'GET:api/v1/classifications/4a668ac6daf74364',
        'json': json.loads(rs('data/cli/classification.json'))
    },
    'classification1_table': {
        'uri': 'GET:api/v1/classifications/4a668ac6daf74364/table',
        'json': {
            "table": [{
                "name": "Salmonella enterica subsp. enterica",
                "rank": "subspecies",
                "readcount": 4642,
                "readcount_w_children": 4960,
                "species_abundance": None,
                "tax_id": 59201
            }]
        }
    },
    'sample1': {
        'uri': 'GET:api/v1/samples/7428cca4a3a04a8e',
        'json': json.loads(rs('data/cli/sample.json'))
    },
    'analyses': {
        'uri': 'GET:api/v1/analyses',
        'json': [json.loads(rs('data/cli/analysis.json'))]
    },
    'samples': {
        'uri': 'GET:api/v1/samples',
        'json': [json.loads(rs('data/cli/sample.json'))]
    },
    'markerpanels': {
        'uri': 'GET:api/v1/markerpanels',
        'json': []
    }
}


@pytest.fixture(scope='function')
def mock_data():
    """Simple mock data for the API, note includes ?schema
    """
    json_data = {
        "GET:api/v1/schema": rs('data/schema.json'),
        "GET:api/v1/tags/fb8e3b693c874f9e": "{\"color\":\"#D4E9ED\",\"name\":\"isolate\",\"$uri\":\"/api/v1/tags/fb8e3b693c874f9e\"}",  # noqa
        "GET:api/v1/classifications/464a7ebcf9f84050/table": json.dumps({
            "table": []
        }),
        "GET:api/v1/classifications/464a7ebcf9f84050": "{\"complete\":true,\"$uri\":\"/api/v1/classifications/464a7ebcf9f84050\",\"created_at\":\"2016-04-26T13:25:38.016211-07:00\",\"success\":true,\"sample\":{\"$ref\":\"/api/v1/samples/7428cca4a3a04a8e\"},\"job\":{\"$ref\":\"/api/v1/jobs/c3caae64b63b4f07\"},\"error_msg\":\"\"}",  # noqa
        "GET:api/v1/analyses/464a7ebcf9f84050": "{\"complete\":true,\"$uri\":\"/api/v1/analyses/464a7ebcf9f84050\",\"created_at\":\"2016-04-26T13:25:38.016211-07:00\",\"success\":true,\"sample\":{\"$ref\":\"/api/v1/samples/7428cca4a3a04a8e\"},\"job\":{\"$ref\":\"/api/v1/jobs/c3caae64b63b4f07\"},\"analysis_type\":\"classification\",\"error_msg\":\"\"}",  # noqa
        "GET:api/v1/samples/7428cca4a3a04a8e": "{\"$uri\":\"/api/v1/samples/7428cca4a3a04a8e\",\"primary_analysis\":{\"$ref\":\"/api/v1/analyses/464a7ebcf9f84050\"},\"created_at\":\"2015-09-25T17:27:19.596555-07:00\",\"tags\":[{\"$ref\":\"/api/v1/tags/42997b7a62634985\"},{\"$ref\":\"/api/v1/tags/fb8e3b693c874f9e\"},{\"$ref\":\"/api/v1/tags/ff4e81909a4348d9\"}],\"filename\":\"SRR2352185.fastq.gz\",\"project\":null,\"owner\":{\"$ref\":\"/api/v1/users/4ada56103d9a48b8\"},\"indexed\":false,\"starred\":false,\"size\":181687821,\"public\":false,\"metadata\":{\"$ref\":\"/api/v1/metadata/a7fc7e430e704e2e\"}}",  # noqa
        "DELETE:api/v1/samples/7428cca4a3a04a8e": "{\"success\": true}",
        "GET:api/v1/tags/ff4e81909a4348d9": "{\"color\":\"#D4E9ED\",\"name\":\"S. enterica\",\"$uri\":\"/api/v1/tags/ff4e81909a4348d9\"}",  # noqa
        "GET:api/v1/tags/42997b7a62634985": "{\"color\":\"#8DCEA8\",\"name\":\"environmental\",\"$uri\":\"/api/v1/tags/42997b7a62634985\"}",  # noqa
        "GET:api/v1/metadata/a7fc7e430e704e2e": json.dumps({
            "$uri": "/api/v1/metadata/a7fc7e430e704e2e",
            "date_collected": "2016-04-26T13:25:38.016211-07:00",
            "date_sequenced": None,
            "description": "PRJNA295366/SRR2352185: environmental swab, state #1, site #1",
            "external_sample_id": None,
            "library_type": None,
            "location_lat": None,
            "location_lon": None,
            "location_string": None,
            "name": "ASM_01 - Salmonella Enteritidis - environmental swab, state #1, site #1",
            "platform": None,
            "sample": {
                "$ref": "/api/v1/samples/7428cca4a3a04a8e"
            },
            "sample_type": None
        })
    }

    with mock_requests(json_data):
        yield


@pytest.fixture(scope='function')
def mock_cli_data():
    """Mock data for CLI tests
    """
    json_data = {}
    for resource in MOCK_DATA.values():
        json_data[resource['uri']] = json.dumps(resource['json'])

    with mock_requests(json_data):
        yield


@pytest.fixture(scope='function')
def upload_mocks():
    def upload_callback(request):
        return (201, {'location': 'on-aws'}, json.dumps({}))

    json_data = {
        "GET:api/v1/schema": rs('data/schema.json'),
        'GET:api/v1/samples/presign_upload': json.dumps({
            'callback_url': '/api/confirm_upload',
            'signing_url': '/s3_sign',
            'url': 'http://localhost:3000/fake_aws_callback'
        }),
        'POST:api/confirm_upload': '',
        'POST:s3_sign': json.dumps({
            'AWSAccessKeyId': 'AKIAI36HUSHZTL3A7ORQ',
            'success_action_status': 201,
            'acl': 'private',
            'key': 'asd/file_ab6276c673814123/myfile.fastq',
            'signature': 'asdjsa',
            'policy': '123123123',
            'x-amz-server-side-encryption': 'AES256'
        }),
        'POST:fake_aws_callback:multipart/form-data': upload_callback,
        'GET:api/v1/samples/init_multipart_upload': json.dumps({
            'callback_url': '/api/import_file_from_s3',
            'file_id': 'abcdef0987654321',
            's3_bucket': 'onecodex-multipart-uploads-encrypted',
            'upload_aws_access_key_id': 'aws_key',
            'upload_aws_secret_access_key': 'aws_secret_key'
        }),
        'POST:api/import_file_from_s3': '',
    }
    with mock_requests(json_data):
        yield


# API FIXTURES
@pytest.fixture(scope='session')
def ocx():
    """Instantiated API client
    """
    schema_mock = {
        "GET:api/v1/schema": rs('data/schema.json')
    }
    with mock_requests(schema_mock):
        ocx = Api(api_key='1eab4217d30d42849dbde0cd1bb94e39',
                  base_url='http://localhost:3000', cache_schema=True)
        return ocx


# CLI / FILE SYSTEM FIXTURE
@pytest.fixture(scope='function')
def mocked_creds_file(monkeypatch, tmpdir):
    # TODO: tmpdir is actually a LocalPath object
    # from py.path, and we coerce it into a string
    # for compatibility with the existing library code
    # *but* we should perhaps *not* do that for
    # better cross-platform compatibility. Investigate
    # and update as needed.
    def mockreturn(path):
        return os.path.join(str(tmpdir), '.onecodex')
    monkeypatch.setattr(os.path, 'expanduser', mockreturn)
