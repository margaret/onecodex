"""
api.py
author: @mbiokyle29

One Codex Api + potion_client subclasses/extensions
"""
from __future__ import print_function
import datetime
import json
import logging
import os

from potion_client import Client as PotionClient
from potion_client.converter import PotionJSONSchemaDecoder
from potion_client.utils import upper_camel_case
from requests.auth import HTTPBasicAuth

from onecodex.lib.auth import BearerTokenAuth
from onecodex.models import _model_lookup

log = logging.getLogger(__name__)


class Api(object):
    """
    This is the base One Codex Api object class. It instantiates a Potion-Client
        object under the hood for making requests.
    """

    def __init__(self, extensions=True, api_key=None,
                 bearer_token=None, cache_schema=True,
                 base_url="http://app.onecodex.com",
                 schema_path="/api/v1/schema"):

        self._req_args = {}
        self._base_url = base_url
        self._schema_path = schema_path

        # Attempt to automatically fetch API key from
        # ~/.onecodex file, API key, or bearer token environment vars
        # *if and only if* no auth is explicitly passed to Api
        #
        # TODO: Consider only doing this if an add'l env var like
        #       'ONE_CODEX_AUTO_LOGIN' or similar is set.
        if api_key is None and bearer_token is None:
            try:
                api_key = json.load(open(os.path.expanduser("~/.onecodex")))["api_key"]
            except:
                pass
            if api_key is None:
                api_key = os.environ.get("ONE_CODEX_API_KEY")
            if bearer_token is None:
                bearer_token = os.environ.get("ONE_CODEX_BEARER_TOKEN")

        if bearer_token:  # prefer bearer token where available
            self._req_args['auth'] = BearerTokenAuth(bearer_token)
        elif api_key:
            self._req_args['auth'] = HTTPBasicAuth(api_key, '')

        # create client instance
        self._client = ExtendedPotionClient(self._base_url, schema_path=self._schema_path,
                                            fetch_schema=False, **self._req_args)
        self._client._fetch_schema(cache_schema=cache_schema)
        self._session = self._client.session
        self._copy_resources()

    def _copy_resources(self):
        """
        Copy all of the resources over to the toplevel client

        -return: populates self with a pointer to each ._client.Resource
        """

        for resource in self._client._resources:
            # set the name param, the keys now have / in them
            potion_resource = self._client._resources[resource]

            oc_cls = _model_lookup[resource]
            oc_cls._api = self
            oc_cls._resource = potion_resource
            setattr(self, oc_cls.__name__, oc_cls)


class ExtendedPotionClient(PotionClient):
    """
    An extention of the PotionClient that caches schema
    """
    DATE_FORMAT = "%Y-%m-%d %H:%M"
    SCHEMA_SAVE_DURATION = 1  # day

    def _fetch_schema(self, extensions=[], cache_schema=True, creds_file=None):
        log.debug('Fetching API JSON schema.')
        creds_fp = os.path.expanduser('~/.onecodex') if creds_file is None else creds_file

        if os.path.exists(creds_fp):
            creds = json.load(open(creds_fp, 'r'))
        else:
            creds = {}

        raw_schema = None
        if cache_schema:
            # Determine if we need to update
            schema_update_needed = True
            last_update = creds.get('schema_saved_at')
            if last_update is not None:
                last_update = datetime.datetime.strptime(last_update, self.DATE_FORMAT)
                time_diff = datetime.datetime.now() - last_update
                schema_update_needed = time_diff.days > self.SCHEMA_SAVE_DURATION

            if not schema_update_needed:
                # get the schema from the credentials file (as a string)
                raw_schema = creds.get('schema')

        if raw_schema is None:
            # Get the schema if it we didn't have it locally
            raw_schema = self.session.get(self._schema_url, params={
                'expand': 'all',
            }).text

        schema = json.loads(raw_schema, cls=PotionJSONSchemaDecoder,
                            referrer=self._schema_url,
                            client=self)

        if cache_schema:
            creds['schema_saved_at'] = datetime.datetime.strftime(datetime.datetime.now(),
                                                                  self.DATE_FORMAT)
            creds['schema'] = raw_schema
        else:
            if 'schema_saved_at' in creds:
                del creds['schema_saved_at']
            if 'schema' in creds:
                del creds['schema']

        # always resave the creds (to make sure we're removing schema if we need to be or
        # saving if we need to do that instead)
        if os.path.exists(creds_fp) and len(creds) > 0:
            json.dump(creds, open(creds_fp, mode='w'))

        for name, resource_schema in schema['properties'].items():
            class_name = upper_camel_case(name)
            setattr(self, class_name, self.resource_factory(name, resource_schema))
