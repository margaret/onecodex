"""
Functions for connecting to the One Codex server; these should be rolled out
into the onecodex python library at some point for use across CLI and GUI clients
"""
from __future__ import print_function

from math import floor
import os
import re
from threading import BoundedSemaphore, Thread

import requests

from onecodex.lib.inline_validator import FASTXTranslator


class UploadException(Exception):
    """
    An exception for when things go wrong with uploading
    """
    pass


MULTIPART_SIZE = 5 * 1000 * 1000 * 1000
DEFAULT_UPLOAD_THREADS = 4
CHUNK_SIZE = 8192


def _wrap_files(filename):
    """
    A little helper to wrap a sequencing file (or join and wrap R1/R2 pairs) and return
    a merged file_object and a "new" filename for the output
    """
    if isinstance(filename, tuple):
        file_obj = FASTXTranslator(open(filename[0], 'rb'), pair=open(filename[1], 'rb'))
        # strip out the _R1_/etc chunk from the first filename if this is a paired upload
        # and make that the filename
        filename = re.sub('[._][Rr][12][._]', '', filename[0])
    else:
        file_obj = FASTXTranslator(open(filename, 'rb'))

    new_filename, ext = os.path.splitext(os.path.basename(filename))
    if ext in {'.gz', '.gzip', '.bz', '.bz2', '.bzip'}:
        new_filename, ext = os.path.splitext(new_filename)

    if ext in {'.fa', '.fna', '.fasta'}:
        ext = '.fa'
    elif ext in {'.fq', '.fastq'}:
        ext = '.fq'

    return file_obj, new_filename + ext + '.gz'


def upload(files, session, samples_resource, server_url, threads=DEFAULT_UPLOAD_THREADS,
           log_to=None):
    """
    Uploads several files to the One Codex server, auto-detecting sizes and using the appropriate
    downstream upload functions. Also, wraps the files with a streaming validator to ensure they
    work.
    """
    file_sizes = []
    for filename in files:
        if isinstance(filename, tuple):
            assert len(filename) == 2
            file_sizes.append(sum(os.path.getsize(f) for f in filename))
        else:
            file_sizes = os.path.getsize(filename)

    # set up the logging
    bar_length = 20
    if log_to is not None:
        log_to.write('Uploading: [{}] 0%'.format('-' * bar_length))
        log_to.flush()

    overall_size = sum(file_sizes)
    transferred_sizes = {}

    def logger(filename, bytes_transferred):
        prev_progress = sum(transferred_sizes.values()) / overall_size
        transferred_sizes[filename] += bytes_transferred
        progress = sum(transferred_sizes.values()) / overall_size
        if floor(bar_length * prev_progress) == floor(bar_length * progress):
            return

        block = int(round(bar_length * progress))
        bar = '#' * block + '-' * (bar_length - block)
        log_to.write('\rUploading: [{}] {:.2f}%'.format(bar, progress * 100))
        log_to.flush()

    # first, upload all the smaller files in parallel (if multiple threads are requested)
    if threads > 1:
        semaphore = BoundedSemaphore(threads)
        upload_threads = []

        def threaded_upload(*args):
            def _wrapped(*wrapped_args):
                semaphore.acquire()
                upload_file(*wrapped_args)
                semaphore.release()

            # TODO: catch exceptions in the thread? or maybe they *are* bubbling out
            thread = Thread(target=_wrapped, args=args)
            thread.start()
            upload_threads.append(thread)
    else:
        threaded_upload = upload_file

    upload_threads = []
    for filename, file_size in zip(files, file_sizes):
        file_obj, filename = _wrap_files(filename)
        if file_size < MULTIPART_SIZE:
            threaded_upload(file_obj, filename, session, samples_resource)

    if threads > 1:
        for thread in upload_threads:
            thread.join()

    # lastly, upload all the very big files sequentially
    for filename, file_size in zip(files, file_sizes):
        file_obj, filename = _wrap_files(filename)
        if file_size >= MULTIPART_SIZE:
            upload_large_file(file_obj, filename, session, samples_resource, server_url,
                              threads=threads)

    if log_to is not None:
        log_to.write('Uploading: Complete.')
        log_to.flush()


def upload_large_file(file_obj, filename, session, samples_resource, server_url, threads=10):
    """
    Uploads a file to the One Codex server via an intermediate S3 bucket (and handles files >5Gb)
    """
    import boto3
    from boto3.s3.transfer import TransferConfig
    from boto3.exceptions import S3UploadFailedError

    # first check with the one codex server to get upload parameters
    try:
        upload_params = samples_resource.read_init_multipart_upload()
    except requests.exceptions.HTTPError:
        raise UploadException('Could not initiate upload with One Codex server')

    callback_url = server_url.rstrip('/') + upload_params['callback_url']
    access_key = upload_params['upload_aws_access_key_id']
    secret_key = upload_params['upload_aws_secret_access_key']

    # actually do the upload
    client = boto3.client('s3', aws_access_key_id=access_key, aws_secret_access_key=secret_key)
    # TODO: this automatically uses 10 threads, but we'd probably like it to be configurable
    config = TransferConfig(max_concurrency=threads)
    try:
        client.upload_fileobj(file_obj, upload_params['s3_bucket'], upload_params['file_id'],
                              extra_args={'ServerSideEncryption': 'AES256'}, config=config)
    except S3UploadFailedError:
        raise UploadException("Upload of %s has failed. Please contact help@onecodex.com "
                              "if you experience further issues" % filename)

    # return completed status to the one codex server
    s3_path = 's3://{}/{}'.format(upload_params['s3_bucket'], upload_params['file_id'])
    req = session.post(callback_url, json={'s3_path': s3_path, 'filename': filename})

    if req.status_code != 200:
        raise UploadException("Upload confirmation of %s has failed. Please contact "
                              "help@onecodex.com if you experience further issues" % filename)


def upload_file(file_obj, filename, session, samples_resource):
    """
    Uploads a file to the One Codex server directly to the users S3 bucket by self-signing
    """
    from requests_toolbelt import MultipartEncoder

    file_size = os.fstat(file_obj.fileno()).st_size
    try:
        upload_info = samples_resource.init_upload({
            'filename': filename,
            'size': file_size,
            'upload_type': 'standard'  # This is multipart form data
        })
    except requests.exceptions.HTTPError:
        raise UploadException(
            "The attempt to initiate your upload failed. Please make "
            "sure you are logged in (`onecodex login`) and try again. "
            "If you continue to experience problems, contact us at "
            "help@onecodex.com for assistance."
        )
    upload_url = upload_info['upload_url']

    # Coerce to str or MultipartEncoder fails
    # Need a list to preserve order for S3
    fields = []
    for k, v in upload_info['additional_fields'].items():
        fields.append((str(k), str(v)))

    fields.append(("file", (filename, file_obj, "text/plain")))
    encoder = MultipartEncoder(fields)

    max_retries = 3
    n_retries = 0
    while n_retries < max_retries:
        try:
            upload_request = session.post(upload_url, data=encoder,
                                          headers={"Content-Type": encoder.content_type},
                                          auth={})
            if upload_request.status_code != 201:
                print("Upload failed. Please contact help@onecodex.com for assistance.")
                raise SystemExit
            break
        except requests.exceptions.ConnectionError:
            n_retries += 1
            if n_retries == max_retries:
                raise UploadException(
                    "The command line client is experiencing connectivity issues and "
                    "cannot complete the upload of %s at this time. Please try again "
                    "later. If the problem persists, contact us at help@onecodex.com "
                    "for assistance." % filename
                )

    # Finally, issue a callback
    try:
        samples_resource.confirm_upload({
            'sample_id': upload_info['sample_id'],
            'upload_type': 'standard'
        })
    except requests.exceptions.HTTPError:
        raise UploadException('Failed to upload: %s' % filename)
