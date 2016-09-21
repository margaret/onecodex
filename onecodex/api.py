"""
api.py
author: @mbiokyle29

One Codex Api + potion_client subclasses/extensions
"""
from __future__ import print_function
from datetime import datetime
import json
import logging
import os

from potion_client import Client as PotionClient
from potion_client.converter import PotionJSONSchemaDecoder, PotionJSONEncoder
from potion_client.resource import Reference
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
                 bearer_token=None, cache_schema=False,
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

        # Create client instance
        # FIXME: Implement an ExtendedPotionClient (see older dev branch)
        #        that properly caches the schema and loads it as appropriate.
        #        Right now, `cache_schema` does not *do anything*
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

    def _fetch_schema(self, extensions=[], cache_schema=False, creds_file=None):
        log.debug('Fetching API JSON schema.')
        creds_fp = os.path.expanduser('~/.onecodex') if creds_file is None else creds_file

        if os.path.exists(creds_fp):
            creds = json.load(open(creds_fp, 'r'))
        else:
            creds = {}

        serialized_schema = None
        if cache_schema:
            # Determine if we need to update
            schema_update_needed = True
            last_update = creds.get('schema_saved_at')
            if last_update is not None:
                last_update = datetime.strptime(last_update, self.DATE_FORMAT)
                time_diff = datetime.now() - last_update
                schema_update_needed = time_diff.days > self.SCHEMA_SAVE_DURATION

            if not schema_update_needed:
                # get the schema from the credentials file (as a string)
                serialized_schema = creds.get('schema')

        if serialized_schema is not None:
            # TODO: if _schema_url isn't in the json, maybe we should fall back to server retrieval?
            base_schema = serialized_schema.pop(self._schema_url)
            schema = json.loads(base_schema, cls=PotionJSONSchemaDecoder, referrer=self._schema_url,
                                client=self)

            self.__cached_instances = []
            for route, route_schema in serialized_schema.items():
                object_schema = json.loads(route_schema, cls=PotionJSONSchemaDecoder,
                                           referrer=self._schema_url, client=self)
                ref = Reference(route, self)
                ref._properties = object_schema
                self.__cached_instances.append(ref)
                self._instances[route] = ref
        else:
            # if the schema wasn't cached or if it was expired, get it anew
            schema = self.session.get(self._schema_url).json(cls=PotionJSONSchemaDecoder,
                                                             referrer=self._schema_url,
                                                             client=self)
            if cache_schema:
                # serialize the schemas back out
                creds['schema_saved_at'] = datetime.strftime(datetime.now(), self.DATE_FORMAT)

                # serialize the main schema
                serialized_schema = {}
                serialized_schema[self._schema_url] = json.dumps(schema, cls=PotionJSONEncoder)

                # serialize the object schemas
                print(schema['properties'].keys())
                for schema_ref in schema['properties'].values():
                    serialized_schema[schema_ref._uri] = json.dumps(schema_ref._properties,
                                                                    cls=PotionJSONEncoder)

                creds['schema'] = serialized_schema
            else:
                if 'schema_saved_at' in creds:
                    del creds['schema_saved_at']
                if 'schema' in creds:
                    del creds['schema']

            # always resave the creds (to make sure we're removing schema if we need to be or
            # saving if we need to do that instead)
            if len(creds) > 0:
                json.dump(creds, open(creds_fp, mode='w'))

        for name, resource_schema in schema['properties'].items():
            class_name = upper_camel_case(name)
            setattr(self, class_name, self.resource_factory(name, resource_schema))
