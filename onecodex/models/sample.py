import requests
from requests.exceptions import HTTPError
from six import string_types

from onecodex.exceptions import OneCodexException
from onecodex.models import OneCodexBase
from onecodex.lib.old_upload import old_upload  # upload_file


class Samples(OneCodexBase):
    _resource_path = '/api/v1/samples'

    @classmethod
    def find(cls, *filters, **keyword_filters):
        instances_route = keyword_filters.get('_instances', 'instances')
        limit = keyword_filters.pop('limit', None)

        # we can only search metadata on our own samples currently
        # FIXME: we need to add `instances_public` and `instances_project` metadata routes to
        # mirror the ones on the samples
        metadata_samples = []
        if instances_route in ['instances']:

            md_schema = next(l for l in SampleMetadata._resource._schema['links']
                             if l['rel'] == instances_route)

            md_where_schema = md_schema['schema']['properties']['where']['properties']
            md_search_keywords = {}
            for keyword in keyword_filters.keys():
                # skip out on $uri to prevent duplicate field searches and the others to
                # simplify the checking below
                if keyword in ['$uri', 'sort', '_instances']:
                    continue
                elif keyword in md_where_schema:
                    md_search_keywords[keyword] = keyword_filters.pop(keyword)

            # TODO: should one be able to sort on metadata? here and on the merged list?
            # md_sort_schema = md_schema['schema']['properties']['sort']['properties']
            # # pull out any metadata sort parameters
            # sort = keyword_filters.get('sort', [])
            # if not isinstance(sort, list):
            #     sort = [sort]
            # passthrough_sort = []
            # for keyword in sort:
            #     if keyword in md_sort_schema:
            #         # TODO: set up sort for metadata
            #         pass
            #     else:
            #         passthrough_sort.append(keyword)
            # keyword_filters['sort'] = passthrough_sort

            if len(md_search_keywords) > 0:
                metadata_samples = [md.sample for md in SampleMetadata.find(**md_search_keywords)]

        samples = []
        if len(metadata_samples) == 0:
            samples = super(Samples, cls).find(*filters, **keyword_filters)

        if len(samples) > 0 and len(metadata_samples) > 0:
            # we need to filter samples to just include stuff from metadata_samples
            metadata_sample_ids = {s.id for s in metadata_samples}
            samples = [s for s in samples if s.id in metadata_sample_ids]
        elif len(metadata_samples) > 0:
            # we have to sort the metadata samples manually using the
            # sort parameters for the samples (and then the metadata parameters?)
            # TODO: implement this (see above block)
            samples = metadata_samples

        return samples[:limit]

    @classmethod
    def find_public(cls, *filters, **keyword_filters):
        keyword_filters['_instances'] = 'instances_public'
        keyword_filters['limit'] = 100
        return cls.find(filters, keyword_filters)

    @classmethod
    def find_project(cls, *filters, **keyword_filters):
        keyword_filters['_instances'] = 'instances_project'
        return cls.find(filters, keyword_filters)

    def save(self):
        """
        Persist changes on this Samples object back to the One Codex server along with any changes
        on its metadata (if it has any).
        """
        super(Samples, self).save()
        if self.metadata is not None:
            self.metadata.save()

    @classmethod
    def upload(cls, filename, threads=None):
        # try:
        #     multipart_req = cls._resource.read_init_multipart_upload()
        # except HTTPError as exc:
        #     if exc.response.status_code != 200:
        #         raise OneCodexException('Could not initial upload with the One Codex server.')
        # TODO: set up progress callback
        # TODO: either raise/wrap UploadException or just us the new one in lib.samples
        # upload_file(filename, cls._resource._client.session, None, 100)

        res = cls._resource
        if isinstance(filename, string_types):
            filename = [filename]
        old_upload(filename, res._client.session, res, res._client._root_url + '/',
                   threads=threads)

        # FIXME: pass the auth into this so we can authenticate the callback?
        # FIXME: return a Sample object?

    def download(self, filename):
        """
        Downloads the original "read" file from the One Codex server.

        This may only work from within notebook sessions and this file is not guaranteed to exist
        for all plan types.
        """
        try:
            url_data = self._resource.download_uri()
            resp = requests.get(url_data['download_uri'], stream=True)
            # TODO: use tqdm or ProgressBar here to display progress?
            with open(filename, 'wb') as f_out:
                for data in resp.iter_content():
                    f_out.write(data)
        except HTTPError as exc:
            if exc.response.status_code == 402:
                raise OneCodexException('Samples must either be enabled for download or you must '
                                        'be in a notebook environment.')


class SampleMetadata(OneCodexBase):
    _resource_path = '/api/v1/metadata'
