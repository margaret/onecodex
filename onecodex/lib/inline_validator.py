import bz2
from collections import deque
import gzip
import re
import string
import warnings


class ValidationError(Exception):
    pass


class ValidationWarning(Warning):
    pass


# buffer code from
# http://stackoverflow.com/questions/2192529/python-creating-a-streaming-gzipd-file-like/2193508
class Buffer(object):
    def __init__(self):
        self._buf = deque()
        self._size = 0

    def __len__(self):
        return self._size

    def write(self, data):
        self._buf.append(data)
        self._size += len(data)

    def read(self, size=-1):
        if size < 0:
            size = self._size
        ret_list = []
        while size > 0 and len(self._buf):
            s = self._buf.popleft()
            size -= len(s)
            ret_list.append(s)
        if size < 0:
            ret_list[-1], remainder = ret_list[-1][:size], ret_list[-1][size:]
            self._buf.appendleft(remainder)
        ret = b''.join(ret_list)
        self._size -= len(ret)
        return ret

    def flush(self):
        pass

    def close(self):
        pass


class GzipBuffer(object):
    def __init__(self):
        self._buf = Buffer()
        self._gzip = gzip.GzipFile(None, mode='wb', fileobj=self._buf)

    def __len__(self):
        return len(self._buf)

    def read(self, size=-1):
        return self._buf.read(size)

    def write(self, s):
        self._gzip.write(s)

    def close(self):
        self._gzip.close()


def _temp_patch_read(file_obj, patch_byte):
    real_read = file_obj.read

    def fake_read(self, n):
        # switch back to the read reading function
        self.read = real_read
        # and return the fake byte, plus whatever else was asked for
        return patch_byte + self.read(n - 1)

    file_obj.read = fake_read


WHITESPACE = string.whitespace.encode()
OTHER_BASES = set(b'UuXx')
if hasattr(bytes, 'maketrans'):
    OTHER_BASE_TRANS = bytes.maketrans(b'UuXx', b'TtNn')
else:
    OTHER_BASE_TRANS = string.maketrans(b'UuXx', b'TtNn')


class FASTXNuclIterator():
    def __init__(self, file_obj, allow_iupac=False, check_filename=True, as_raw=False):
        self._set_file_obj(file_obj, check_filename=check_filename)

        self.unchecked_buffer = b''
        self.buffer_read_size = 2048
        self.seq_reader = self._generate_seq_reader(False)

        if allow_iupac:
            self.valid_bases = set(b'ABCDGHIKMNRSTUVWXYabcdghikmnrstuvwxy' +
                                   string.whitespace.encode())
        else:
            self.valid_bases = set(b'ACGTNUXacgtnux' + string.whitespace.encode())
        self.as_raw = as_raw
        self.warnings = set()

    def _set_file_obj(self, file_obj, check_filename=True):
        """
        Transparently decompress files and determine what kind of file they are (FASTA/Q)
        """
        if not hasattr(file_obj, 'name'):
            # can't do the checks if there's not filename
            check_filename = False

        # detect if gzipped/bzipped and uncompress transparently
        start = file_obj.read(1)
        if start == b'\x1f':
            if check_filename and not file_obj.name.endswith('.gz', '.gzip'):
                raise ValidationError('File is gzipped, but lacks a ".gz" ending')
            _temp_patch_read(file_obj, b'\x1f')
            file_obj = gzip.open(file_obj)
            start = file_obj.read(1)
        elif start == b'\x42' and hasattr(bz2, 'open'):
            if check_filename and not file_obj.name.endswith(('.bz2', '.bz', '.bzip')):
                raise ValidationError('File is bzipped, but lacks a ".bz2" ending')
            # we can only read BZ2 files in python 3.3 and above
            _temp_patch_read(file_obj, b'\x42')
            file_obj = bz2.open(file_obj)
            start = file_obj.read(1)

        # determine if a FASTQ or a FASTA
        if start == b'>':
            self.file_type = 'FASTA'
            if check_filename and not ('.fa' in file_obj.name or
                                       '.fna' in file_obj.name or
                                       '.fasta' in file_obj.name):
                raise ValidationError('File is FASTA, but lacks a ".fa" ending')
        elif start == b'@':
            self.file_type = 'FASTQ'
            if check_filename and not ('.fq' in file_obj.name or
                                       '.fastq' in file_obj.name):
                raise ValidationError('File is FASTQ, but lacks a ".fq" ending')
        else:
            raise ValidationError('File is not valid FASTX')

        self.file_obj = file_obj

    def _generate_seq_reader(self, last=False):
        # the last record doesn't have a @/> on the next line so we omit that
        # if the "last" flag is passed (to allow reading the last record)
        if self.file_type == 'FASTA':
            seq_reader = re.compile(b"""
                (?P<id>[^\n]+)\n  # the identifier line
                (?P<seq>[^>]+)  # the sequence
                {}
            """.format('' if last else '(?:\n>)'), re.VERBOSE)
        elif self.file_type == 'FASTQ':
            seq_reader = re.compile(b"""
                (?P<id>[^\n]+)\n
                (?P<seq>[^\n]+)\n
                \+(?P<id2>[^\n]*)\n
                (?P<qual>[^\n]+)
                {}
            """.format('' if last else '(?:\n@)'), re.DOTALL + re.VERBOSE)
        return seq_reader

    def _warn_once(self, message):
        if message in self.warnings:
            return
        warnings.warn(message, ValidationWarning)
        self.warnings.add(message)

    def _validate_record(self, rec):
        # TODO: if there are quality scores, make sure they're in range
        # FIXME: fail if reads aren't interleaved and an override flag isn't passed?
        seq_id, seq, qual = rec['id'], rec['seq'], rec.get('qual')
        if b'\t' in seq_id:
            self._warn_once('File can not have tabs in headers; autoreplacing')
            seq_id = seq_id.replace('\t', '|')
        set_seq = set(seq)
        if not set_seq.issubset(self.valid_bases):
            raise ValidationError('File contains non-nucleic acid sequence characters')
        if set_seq.intersection(WHITESPACE):
            # TODO: everything has newlines in it b/c of the way the regexs are set up
            # maybe we should fix this so we can warn on it?
            seq = seq.translate(None, WHITESPACE)
        if set_seq.intersection(OTHER_BASES):
            self._warn_once('Translating other bases (X->N,U->T)')
            seq = seq.translate(OTHER_BASE_TRANS)
        return seq_id, seq, qual

    def __iter__(self):
        eof = False
        while not eof:
            new_data = self.file_obj.read(self.buffer_read_size)
            # if we're at the end of the file
            if len(new_data) == 0:
                # switch to a different regex to parse without a next record
                eof = True
                self.seq_reader = self._generate_seq_reader(True)
            else:
                self.unchecked_buffer += new_data

            end = 0
            for match in self.seq_reader.finditer(self.unchecked_buffer):
                rec = match.groupdict()
                seq_id, seq, qual = self._validate_record(rec)
                # FIXME: there are newlines sneaking in somewhere?
                if self.as_raw:
                    yield (seq_id, seq, qual)
                elif self.file_type == 'FASTA':
                    yield '>{}\n{}\n'.format(seq_id, seq)
                elif self.file_type == 'FASTQ':
                    yield '@{}\n{}\n+\n{}\n'.format(seq_id, seq, qual)
                end = match.end()

            self.unchecked_buffer = self.unchecked_buffer[end:]


class FASTXTranslator():
    def __init__(self, file_obj, pair=None, recompress=True, **kwargs):
        # detect if gzipped/bzipped and uncompress transparently
        reads = FASTXNuclIterator(file_obj, **kwargs)
        self.reads = iter(reads)
        if pair is not None:
            reads_pair = FASTXNuclIterator(pair)
            self.reads_pair = iter(reads_pair)
            if reads.file_type != reads_pair.file_type:
                raise ValidationError('Paired files are different types (FASTA/FASTQ)')
        else:
            self.reads_pair = None

        if recompress:
            self.checked_buffer = GzipBuffer()
        else:
            self.checked_buffer = Buffer()

    def read(self, n=-1):
        while len(self.checked_buffer) < n or n < 0:
            try:
                record = next(self.reads)
            except StopIteration:
                record = None

            if self.reads_pair is not None:
                try:
                    record_pair = next(self.reads_pair)
                except StopIteration:
                    record_pair = None

                if record is not None and record_pair is not None:
                    self.checked_buffer.write(record)
                    self.checked_buffer.write(record_pair)
                elif record is None and record_pair is None:
                    self.checked_buffer.close()
                    break
                else:
                    raise ValidationError('Paired read files are not the same length')
            else:
                if record is not None:
                    self.checked_buffer.write(record)
                elif record is None:
                    self.checked_buffer.close()
                    break

        return self.checked_buffer.read(n)

    def readall(self):
        return self.read()

    def write(self, b):
        raise NotImplementedError()
