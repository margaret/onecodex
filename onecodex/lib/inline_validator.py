import bz2
from collections import deque
import gzip
import os
import re
import string
import warnings

from onecodex.exceptions import ValidationError, ValidationWarning


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


OTHER_BASES = set(b'UuXx')
if hasattr(bytes, 'maketrans'):
    OTHER_BASE_TRANS = bytes.maketrans(b'UuXx', b'TtNn')
else:
    OTHER_BASE_TRANS = string.maketrans(b'UuXx', b'TtNn')


class FASTXNuclIterator():
    def __init__(self, file_obj, allow_iupac=False, check_filename=True, as_raw=False):
        self._set_file_obj(file_obj, check_filename=check_filename)

        self.unchecked_buffer = b''
        self.buffer_read_size = 1024 * 1024 * 16  # 16MB
        self.seq_reader = self._generate_seq_reader(False)

        if allow_iupac:
            self.valid_bases = set(b'ABCDGHIKMNRSTUVWXYabcdghikmnrstuvwxy' +
                                   string.whitespace.encode())
        else:
            self.valid_bases = set(b'ACGTNUXacgtnux' + string.whitespace.encode())
        self.as_raw = as_raw

        if hasattr(file_obj, 'name'):
            self.name = file_obj.name
        else:
            self.name = 'File'

        try:
            total_size = os.fstat(file_obj.fileno()).st_size
            if total_size < 70:
                raise ValidationError('{} is too small to be analyzed: {} bytes'.format(
                    self.name, total_size
                ))
        except IOError:
            pass
        self.processed_size = 0

        self.warnings = set()

    def _set_file_obj(self, file_obj, check_filename=True):
        """
        Transparently decompress files and determine what kind of file they are (FASTA/Q).
        """
        if not hasattr(file_obj, 'name'):
            # can't do the checks if there's not filename
            check_filename = False

        # detect if gzipped/bzipped and uncompress transparently
        start = file_obj.read(1)
        if start == b'\x1f':
            if check_filename and not file_obj.name.endswith(('.gz', '.gzip')):
                raise ValidationError('{} is gzipped, but lacks a ".gz" ending'.format(self.name))
            file_obj.seek(0)
            file_obj = gzip.GzipFile(fileobj=file_obj)
            start = file_obj.read(1)
        elif start == b'\x42' and hasattr(bz2, 'open'):
            if check_filename and not file_obj.name.endswith(('.bz2', '.bz', '.bzip')):
                raise ValidationError('{} is bzipped, but lacks a ".bz2" ending'.format(self.name))
            # we can only read BZ2 files in python 3.3 and above
            file_obj.seek(0)
            file_obj = bz2.open(file_obj)
            start = file_obj.read(1)

        # determine if a FASTQ or a FASTA
        if start == b'>':
            self.file_type = 'FASTA'
            if check_filename and not ('.fa' in file_obj.name or
                                       '.fna' in file_obj.name or
                                       '.fasta' in file_obj.name):
                raise ValidationError('{} is FASTA, but lacks a ".fa" ending'.format(self.name))
        elif start == b'@':
            self.file_type = 'FASTQ'
            if check_filename and not ('.fq' in file_obj.name or
                                       '.fastq' in file_obj.name):
                raise ValidationError('{} is FASTQ, but lacks a ".fq" ending'.format(self.name))
        else:
            raise ValidationError('{} is not valid FASTX'.format(self.name))

        self.file_obj = file_obj

    def _generate_seq_reader(self, last=False):
        # the last record doesn't have a @/> on the next line so we omit that
        # if the "last" flag is passed (to allow reading the last record)
        if self.file_type == 'FASTA':
            seq_reader = re.compile(b"""
                (?P<id>[^\\n]+)\\n  # the identifier line
                (?P<seq>[^>]+)  # the sequence
                {}
            """.format('' if last else '(?:\\n>)'), re.VERBOSE)
        elif self.file_type == 'FASTQ':
            seq_reader = re.compile(b"""
                (?P<id>[^\\n]+)\\n
                (?P<seq>[^\\n]+)\\n
                \+(?P<id2>[^\\n]*)\\n
                (?P<qual>[^\\n]+)
                {}
            """.format('' if last else '(?:\\n@)'), re.DOTALL + re.VERBOSE)
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
            self._warn_once('{} can not have tabs in headers; autoreplacing'.format(self.name))
            seq_id = seq_id.replace('\t', '|')
        set_seq = set(seq)
        if not set_seq.issubset(self.valid_bases):
            chars = ','.join(set_seq.difference(self.valid_bases))
            raise ValidationError('{} contains non-nucleic acid characters: {}'.format(self.name,
                                                                                       chars))
        if set_seq.intersection(OTHER_BASES):
            self._warn_once('Translating other bases in {} (X->N,U->T)'.format(self.name))
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
                # automatically remove newlines from the end of the file (they get added back in
                # by the formatting operation below, but otherwise they mess up the regex and you
                # end up with two terminating \n's)
                self.unchecked_buffer = self.unchecked_buffer.rstrip('\n')
            else:
                self.unchecked_buffer += new_data

            end = 0
            while True:
                match = self.seq_reader.match(self.unchecked_buffer, end)
                if match is None:
                    break
                rec = match.groupdict()
                seq_id, seq, qual = self._validate_record(rec)
                if self.as_raw:
                    yield (seq_id, seq, qual)
                elif self.file_type == 'FASTA':
                    yield '>{}\n{}\n'.format(seq_id, seq)
                elif self.file_type == 'FASTQ':
                    yield '@{}\n{}\n+\n{}\n'.format(seq_id, seq, qual)
                end = match.end()

            self.processed_size += end
            self.unchecked_buffer = self.unchecked_buffer[end:]


class FASTXTranslator():
    def __init__(self, file_obj, pair=None, recompress=True, progress_callback=None, **kwargs):
        # detect if gzipped/bzipped and uncompress transparently
        self.reads = FASTXNuclIterator(file_obj, **kwargs)
        self.reads_iter = iter(self.reads)
        if pair is not None:
            self.reads_pair = FASTXNuclIterator(pair)
            self.reads_pair_iter = iter(self.reads_pair)
            if self.reads.file_type != self.reads_pair.file_type:
                raise ValidationError('Paired files are different types (FASTA/FASTQ)')
        else:
            self.reads_pair = None
            self.reads_pair_iter = None

        if recompress:
            self.checked_buffer = GzipBuffer()
        else:
            self.checked_buffer = Buffer()

        self.progress_callback = progress_callback
        self.total_written = 0

    def read(self, n=-1):
        if self.reads_pair is None:
            while len(self.checked_buffer) < n or n < 0:
                try:
                    record = next(self.reads_iter)
                except StopIteration:
                    record = None

                if record is not None:
                    self.total_written += len(record)
                    self.checked_buffer.write(record)
                elif record is None:
                    self.checked_buffer.close()
                    break

                if self.progress_callback is not None:
                    self.progress_callback(self.reads.name, self.reads.processed_size)
        else:
            while len(self.checked_buffer) < n or n < 0:
                try:
                    record = next(self.reads_iter)
                except StopIteration:
                    record = None
                try:
                    record_pair = next(self.reads_pair_iter)
                except StopIteration:
                    record_pair = None

                if record is not None and record_pair is not None:
                    self.total_written += len(record) + len(record_pair)
                    self.checked_buffer.write(record)
                    self.checked_buffer.write(record_pair)
                elif record is None and record_pair is None:
                    self.checked_buffer.close()
                    break
                else:
                    raise ValidationError('Paired read files are not the same length')

                if self.progress_callback is not None:
                    if self.reads_pair is not None:
                        bytes_uploaded = self.reads.processed_size + self.reads_pair.processed_size
                    else:
                        bytes_uploaded = self.reads.processed_size
                    self.progress_callback(self.reads.name, bytes_uploaded)

        return self.checked_buffer.read(n)

    def readall(self):
        return self.read()

    def tell(self):
        return self.total_written

    def write(self, b):
        raise NotImplementedError()
