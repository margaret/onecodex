from __future__ import print_function
from onecodex import Api


def test_api_fixture(ocx):
    assert isinstance(ocx, Api)


def test_api_creation(mock_data):
    ocx = Api(api_key='1eab4217d30d42849dbde0cd1bb94e39',
              base_url='http://localhost:3005', cache_schema=False)
    assert isinstance(ocx, Api)
    assert True


def test_sample_get(ocx, mock_data):
    sample = ocx.Samples.get('7428cca4a3a04a8e')
    assert sample.size == 181687821
    assert sample.filename == 'SRR2352185.fastq.gz'

    analysis = sample.primary_analysis
    assert analysis
    assert analysis.complete

    tags = sample.tags
    assert len(tags) > 1
    assert 'isolate' in [t.name for t in tags]
