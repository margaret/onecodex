"""
api.py
author: @mbiokyle29

One Codex Api + potion_client subclasses/extensions
"""
from __future__ import print_function
import json
import logging
import os

from potion_client import Client as PotionClient
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
        self._client = PotionClient(self._base_url, schema_path=self._schema_path,
                                    fetch_schema=False, **self._req_args)
        self._client._fetch_schema()
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
