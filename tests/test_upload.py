from io import BytesIO

import pytest

from onecodex.lib.inline_validator import FASTXNuclIterator, FASTXTranslator


def test_nucl_iterator():
    fakefile = BytesIO(b'>test\nACGT\n')
    iterator = iter(FASTXNuclIterator(fakefile))
    val = next(iterator)
    assert val == '>test\nACGT\n'
    with pytest.raises(StopIteration):
        next(iterator)


def test_paired_validator():
    # test a single file
    fakefile = BytesIO(b'>test\nACGT\n')
    outfile = FASTXTranslator(fakefile, recompress=False)
    assert outfile.read() == b'>test\nACGT\n'

    # test a single file without an ending newline
    fakefile = BytesIO(b'>test\nACGT')
    outfile = FASTXTranslator(fakefile, recompress=False)
    assert outfile.read() == b'>test\nACGT\n'

    # test paired files
    fakefile = BytesIO(b'>test\nACGT\n')
    fakefile2 = BytesIO(b'>test2\nTGCA\n')
    outfile = FASTXTranslator(fakefile, pair=fakefile2, recompress=False)
    assert outfile.read() == b'>test\nACGT\n>test2\nTGCA\n'

    # test compression works
    fakefile = BytesIO(b'>test\nACGT\n')
    outfile = FASTXTranslator(fakefile)
    outdata = outfile.read()

    # there's a 4-byte timestamp in the middle of the gziped data so we check the start and end
    assert outdata.startswith(b'\x1f\x8b\x08\x00')
    assert outdata.endswith(b'\x02\xff\xb3+I-.\xe1rtv\x0f\xe1\x02\x00\xf3\x1dK\xc4\x0b\x00\x00\x00')
