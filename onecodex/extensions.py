"""
extensions.py
author: @mbiokyle29
"""
from __future__ import print_function
import logging
import datetime
from collections import defaultdict, OrderedDict

import pandas as pd
from potion_client.resource import Resource

log = logging.getLogger(__name__)


class SamplesExtensions(Resource):
    _extends = ["Samples"]


class AnalysesExtensions(Resource):
    _extends = ["Analyses"]


class ClassificationsExtensions(Resource):
    _extends = ["Classifications"]

    otu_format = "Biological Observation Matrix 0.9.1-dev"
    otu_url = "http://biom-format.org/documentation/format_versions/biom-1.0.html"  # noqa
    _table = None

    @classmethod
    def to_otu(cls, classifications):
        """
        Converts a list of classifications into a dictionary resembling
            an OTU table.
        """

        otu = OrderedDict({'format': cls.otu_format,
                           'format_url': cls.otu_url,
                           'type': "OTU table",
                           'generated_by': "One Codex API V1",
                           'date': datetime.datetime.now().isoformat(),
                           'rows': [],
                           'columns': [],
                           'matrix_type': "sparse",
                           'matrix_element_type': "int"})

        rows = defaultdict(dict)
        for classification in classifications:
            col_id = len(otu['columns'])  # 0 index
            columns_entry = {"id": str(classification.id)}
            otu['columns'].append(columns_entry)
            sample_df = classification.table_df()

            for tax_id in sample_df['tax_id']:
                rows[tax_id][col_id] = int(
                    sample_df[sample_df['tax_id'] == tax_id]['readcount'])

        num_rows = len(rows)
        num_cols = len(otu['columns'])

        otu['shape'] = [num_rows, num_cols]
        otu['data'] = []

        for present_taxa in sorted(rows):
            # add the row entry
            row_id = len(otu['rows'])
            otu['rows'].append({"id": present_taxa})

            for sample_with_hit in rows[present_taxa]:
                counts = rows[present_taxa][sample_with_hit]
                otu['data'].append([row_id, sample_with_hit, counts])

        return otu

    def table_df(self):
        """
        Return the complete results table for the classification.
        Note that self._table starts as undefined
        and only will be set once as needed
        """
        while self._table is None:
            self._table = pd.DataFrame(self.table()['table'])
        return self._table

    def abundances_df(self, ids=None):
        """
        Query the results table to get abundance data for all or some tax ids
        """

        if ids is None:
            # get the data frame
            return self.table_df()

        else:
            res = self.table_df()
            return res[res['tax_id'].isin(ids)]


class MarkerpanelsExtensions(Resource):
    _extends = ["Markerpanels"]


class MetadataExtensions(Resource):
    _extends = ["Metadata"]


class TagsExtensions(Resource):
    _extends = ["Tags"]


class UsersExtensions(Resource):
    _extends = ["Users"]


extensions = [SamplesExtensions, AnalysesExtensions,
              ClassificationsExtensions, MarkerpanelsExtensions,
              MetadataExtensions, TagsExtensions, UsersExtensions]
