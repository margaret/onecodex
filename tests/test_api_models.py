from __future__ import print_function
import datetime
import pandas as pd

import onecodex
from onecodex import Api
from onecodex.exceptions import MethodNotSupported
import pytest


def test_api_creation(mock_data):
    ocx = Api(api_key='1eab4217d30d42849dbde0cd1bb94e39',
              base_url='http://localhost:3005', cache_schema=False)
    assert isinstance(ocx, Api)
    assert True


def test_sample_get(ocx, mock_data):
    sample = ocx.Samples.get('7428cca4a3a04a8e')
    assert sample.size == 181687821
    assert sample.filename == 'SRR2352185.fastq.gz'
    assert sample.__repr__() == "<Samples 7428cca4a3a04a8e>"
    assert isinstance(sample.created_at, datetime.datetime)

    analysis = sample.primary_analysis
    assert analysis
    assert analysis.complete

    tags = sample.tags
    assert len(tags) > 1
    assert 'isolate' in [t.name for t in tags]


def test_get_failure_instructions(ocx):
    with pytest.raises(TypeError):
        ocx.Samples('direct_id')


def test_model_deletions(ocx, mock_data):
    sample = ocx.Samples.get('7428cca4a3a04a8e')
    sample.delete()

    analysis = sample.primary_analysis
    with pytest.raises(MethodNotSupported):
        analysis.delete()


def test_model_updates(ocx, mock_data):
    sample = ocx.Samples.get('7428cca4a3a04a8e')
    sample.starred = not sample.starred

    # Read-only field
    with pytest.raises(MethodNotSupported):
        sample.public = not sample.public

    # No update resource
    analysis = sample.primary_analysis
    with pytest.raises(MethodNotSupported):
        analysis.created_at = datetime.datetime.utcnow()


def test_metadata_saving(ocx, mock_data):
    sample = ocx.Samples.get('7428cca4a3a04a8e')
    metadata1 = sample.metadata
    metadata2 = ocx.SampleMetadata.get('a7fc7e430e704e2e')
    assert metadata1 == metadata2
    assert isinstance(metadata2.date_collected, datetime.datetime)


def test_dir_patching(ocx, mock_data):
    sample = ocx.Samples.get('7428cca4a3a04a8e')
    props = {'id', 'created_at', 'filename', 'indexed', 'public',
             'metadata', 'owner', 'primary_analysis', 'project',
             'size', 'starred', 'tags'}
    for prop in props:
        assert prop in dir(sample)
    assert len(sample.__dict__) == 1  # I'm not sure we *want* this...


def test_classification_methods(ocx, mock_data):
    classification = ocx.Classifications.get('464a7ebcf9f84050')
    assert isinstance(classification, onecodex.models.analysis.Classifications)
    t = classification.table()
    assert isinstance(t, pd.DataFrame)
