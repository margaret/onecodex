from onecodex import Api
from onecodex.lib.auth import BearerTokenAuth
from requests.auth import HTTPBasicAuth


def test_bearer_auth_from_env(mock_data, monkeypatch):
    monkeypatch.setenv('ONE_CODEX_BEARER_TOKEN', 'mysecrettoken')
    ocx = Api(cache_schema=True, base_url="http://localhost:3000")
    assert isinstance(ocx._req_args['auth'], BearerTokenAuth)
    sample = ocx.Samples.get('7428cca4a3a04a8e')
    assert sample.public is False


def test_api_key_auth_from_env(mock_data, monkeypatch):
    monkeypatch.setenv('ONE_CODEX_API_KEY', 'mysecretkey')
    ocx = Api(cache_schema=True)
    assert isinstance(ocx._req_args['auth'], HTTPBasicAuth)


def test_bearer_auth_from_kwargs(mock_data):
    ocx = Api(bearer_token='mysecrettoken', cache_schema=True)
    assert isinstance(ocx._req_args['auth'], BearerTokenAuth)


def test_api_key_auth_from_kwargs(mock_data):
    ocx = Api(api_key='mysecretkey', cache_schema=True)
    assert isinstance(ocx._req_args['auth'], HTTPBasicAuth)
