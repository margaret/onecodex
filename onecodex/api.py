"""
api.py
author: @mbiokyle29

One Codex Api + potion_client subclasses/extensions
"""
from __future__ import print_function
import datetime
import json
import logging
import os
import sys
from multiprocessing import Lock, Value
from threading import BoundedSemaphore, Thread

import requests
from potion_client import Client as PotionClient
from potion_client.converter import PotionJSONSchemaDecoder
from potion_client.utils import upper_camel_case
from requests.auth import HTTPBasicAuth
from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor

from onecodex.query import get, where
from onecodex.utils import check_for_allowed_file, warn_if_insecure_platform

# Use multipart upload for anything over ~5GB
# (a little bit smaller bc 1000^3, not 1024^3)
MULTIPART_SIZE = 5 * 1000 * 1000 * 1000
DEFAULT_UPLOAD_THREADS = 4
CHUNK_SIZE = 8192

log = logging.getLogger(__name__)


class Api(object):
    """
    This is the base One Codex Api object class. It instantiates a Potion-Client
        object under the hood for making requests.
    """

    def __init__(self, extensions=True, api_key=None,
                 cache_schema=False,
                 base_url="http://app.onecodex.com",
                 schema_path="/api/v1/schema"):

        self.ext = []
        self.req_args = {}
        self.base_url = base_url
        self.schema_path = schema_path

        if extensions:
            try:
                from .extensions import extensions as ext
                self.ext = ext

            except ImportError as e:
                log.warn("Import Error Occured for Api Extensions!")
                log.warn("Please install onecodex libary with extensions")
                log.warn(e)

        if api_key:
            self.req_args['auth'] = HTTPBasicAuth(api_key, '')

        # create client instance
        self._client = ExtendedPotionClient(self.base_url, schema_path=self.schema_path,
                                            fetch_schema=False, **self.req_args)
        self._client._fetch_schema(extensions=self.ext, cache_schema=cache_schema)
        self._session = self._client.session
        self._copy_resources()

    def _copy_resources(self):
        """
        Copy all of the resources over to the toplevel client
            and give them their .get, .where and .json methods

        -return: populates self with a pointer to each ._client.Resource
        """

        for resource in self._client._resources:

            # set the name param, the keys now have / in them
            name = self._client._resources[resource].__name__
            setattr(self, name, self._client._resources[resource])

            # fetch the added name
            # add the get function
            resource = getattr(self, name)
            setattr(resource, "get", classmethod(get))
            setattr(resource, "where", classmethod(where))

    def upload(self, files, threads=DEFAULT_UPLOAD_THREADS):
        """
        This is the entry point for the upload flow. It will determine
            what approach to take with uploading and pass to other functions

        -param list files: The list of file (paths) to upload
        -param int threads: Number of upload threads to use (def=4)
        """

        # check insecure platform, disable warnigns
        if warn_if_insecure_platform():
            logging.captureWarnings(True)

        file_sizes = [os.path.getsize(f) for f in files]
        if min(file_sizes) < 35:
            print("Cannot upload empty files. Please check that all files "
                  "contain sequence data and try again.")
            raise SystemExit

        max_file_size = max(file_sizes)
        if max_file_size > MULTIPART_SIZE:
            for ix, f in enumerate(files):
                if file_sizes[ix] > MULTIPART_SIZE:
                    self._upload_multipart(f)
                else:
                    self._upload_direct([f], threads)
        else:
            self._upload_direct(files, threads)

    def _upload_multipart(self, file):
        """
        This is the upload function for files over 5GB. It uploads them serially
            to s3 using awscli. It will exit if awscli is not installed

        -param str file: The path to the file to upload
        """
        check_for_allowed_file(file)
        multipart_req = self._client.Samples.read_init_multipart_upload()

        s3_bucket = multipart_req["s3_bucket"]
        callback_chunk = multipart_req['callback_url']
        callback_url = self.base_url.rstrip("/") + callback_chunk
        file_id = multipart_req["file_id"]
        aws_access_key_id = multipart_req["upload_aws_access_key_id"]
        aws_secret_access_key = multipart_req["upload_aws_secret_access_key"]  # noqa

        # Upload to s3 using boto
        try:
            import awscli  # noqa
            import subprocess
        except ImportError:
            print("You must install the awscli package for files >5GB in size. "  # noqa
                      "On most systems, it can be installed with `pip install awscli`.")  # noqa
            raise SystemExit

        s3_path = "s3://" + s3_bucket + "/" + file_id
        print("Starting large (>5GB) file upload. "
              "Please be patient while the file transfers...")
        try:
            # We want to only get output from onecodex
            p = subprocess.Popen("AWS_ACCESS_KEY_ID=%s AWS_SECRET_ACCESS_KEY=%s aws s3 cp %s %s --sse" %
                                 (aws_access_key_id, aws_secret_access_key, file, s3_path),
                                 shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

            print("\n"
                  "    ###########################################################\n"
                  "    ###           Uploading large multipart file            ###\n"
                  "    ###                Upload output below...               ###\n"
                  "    ###########################################################\n")
            while p.poll() is None:
                char = p.stdout.read(1)
                sys.stdout.write(char)
                sys.stdout.flush()

        except KeyboardInterrupt:
            log.info("Upload successfully cancelled. Quitting.")
            p.sigterm()
            raise SystemExit

        if p.returncode != 0:
            print("An error occured uploading %s using the aws-cli." % file)
            raise SystemExit

        callback_request = self._session.post(callback_url,
                                              headers={"Content-Type": "application/json"},
                                              data=json.dumps({"s3_path": s3_path,
                                                               "filename": os.path.basename(file)}))

        if callback_request.status_code != 200:
            print("Upload of %s failed. Please contact help@onecodex.com "
                  "if you experience further issues." % file)
            sys.exit(1)
        print("Successfully uploaded: %s\n" % file)
        print("    ###########################################################\n"
              "    ### Please note: Large file uploads may take several    ###\n"
              "    ### minutes to appear on the One Codex website. If a    ###\n"
              "    ### file does not appear after a longer period of time, ###\n"
              "    ### however, please contact us at help@onecodex.com.    ###\n"
              "    ###########################################################\n")

    def _upload_direct(self, files, threads):
        """
        This is the upload method for files < 5GB. They are sent directly
            with requests and using the threads

        -param list files: The list of filepaths to upload
        -param int threads: Number of threads to use
        """

        if threads > 1:
            semaphore = BoundedSemaphore(threads)
        if threads != DEFAULT_UPLOAD_THREADS:
            print("Uploading with up to %d thread(s)." % threads)

        # Get the initially needed routes
        routes = self._client.Samples.read_presign_upload()

        # parse out routes
        s3_url = routes['url']
        signing_url = self.base_url.rstrip("/") + routes['signing_url']
        callback_url = self.base_url.rstrip("/") + routes['callback_url']

        upload_threads = []
        upload_progress_bytes = Value('L', 0)
        upload_progress_lock = Lock()
        total_bytes = sum([os.path.getsize(f) for f in files])
        total_files = Value('i', len(files))

        for f in files:
            if threads > 1 and len(files) > 1:  # parallel uploads
                # Multi-threaded uploads
                t = Thread(target=self._upload_helper,
                           args=(f, s3_url, signing_url, callback_url,
                                 upload_progress_bytes, upload_progress_lock,
                                 total_bytes, total_files, semaphore))
                upload_threads.append(t)
                t.start()
            else:  # serial uploads
                self._upload_helper(f, s3_url, signing_url, callback_url,
                                    upload_progress_bytes, upload_progress_lock,
                                    total_bytes, total_files)

            if threads > 1:
                for ut in upload_threads:
                    ut.join()

    def _upload_helper(self, file, s3_url, signing_url, callback_url,
                       upload_progress_bytes, upload_progress_lock,
                       total_bytes, total_files, semaphore=None):
        """
        This is the tread worker function for direct uploads. It makes several
            calls to the app server to sign the upload and record success.
            It also passes byte amount info to the callback for prograss bar

        -param str file: The filepath to be uploaded in this thread
        -param str s3_url: The signed s3 bucket url to upload to
        -param str signing_url: The url to post the signing request too
        -param str callback_url: Url to post successful upload notice too
        -param int upload_progress_bytes: Bytes uploaded so far
        -param Lock upload_progress_lock: The thread lock
        -param int total_bytes: Total bytes left to upload
        -param int total_files: Total number of files to upload
        -param BoundedSemaphore semaphore: Count of threads in existence

        """

        # First get the signing form data
        if semaphore is not None:
            semaphore.acquire()

        stripped_filename = os.path.basename(file)
        signing_request = self._session.post(signing_url,
                                            data={"filename": stripped_filename,
                                                  "via_api": "true"},
                                            headers={"x-amz-server-side-encryption": "AES256"})  # noqa

        if signing_request.status_code != 200:
            try:
                print("Failed upload: %s" % signing_request.json()["msg"])
            except:
                print("Upload failed. Please contact help@onecodex.com for "
                      "assistance if you continue to experience problems.")
            raise SystemExit

        file_uuid = signing_request.json()['key'].split("/")[-2][5:]

        # Coerce to str or MultipartEncoder fails
        # Need a list to preserve order for S3
        fields = []
        for k, v in signing_request.json().items():
            fields.append((str(k), str(v)))

        fields.append(("file", (stripped_filename, open(file, mode='rb'), "text/plain")))
        e = MultipartEncoder(fields)
        m = MultipartEncoderMonitor(e, lambda x: self._upload_callback(x, upload_progress_bytes,
                                                                       upload_progress_lock,
                                                                       total_bytes=(total_bytes + 8192),
                                                                       n_files=total_files))

        max_retries = 3
        n_retries = 0
        while n_retries < max_retries:
            try:
                upload_request = self._session.post(s3_url, data=m, headers={"Content-Type": m.content_type},
                                                    auth={})
                if upload_request.status_code != 201:
                    print("Upload failed. Please contact help@onecodex.com for assistance.")
                    raise SystemExit
                break
            except requests.exceptions.ConnectionError:
                n_retries += 1
                if n_retries == max_retries:
                    print("The command line client is experiencing connectivity issues and "
                          "cannot complete the upload of %s at this time. Please try again "
                          "later. If the problem persists, contact us at help@onecodex.com "
                          "for assistance." % stripped_filename)
                    raise SystemExit

        # Finally, issue a callback
        callback_request = self._session.post(callback_url, data={
            "location": upload_request.headers['location'],
            "size": os.path.getsize(file)
        })

        if callback_request.status_code == 200:
            success_msg = "Successfully uploaded: %s. File ID is: %s." % (file, file_uuid)
            if upload_progress_bytes.value == -1:  # == -1 upon completion
                print(success_msg)
            else:
                sys.stderr.write("\r")
                sys.stderr.flush()
                print(success_msg)
            with upload_progress_lock:
                total_files.value -= 1
        else:
            print("Failed to upload: %s" % file)
            raise SystemExit

        if semaphore is not None:
            semaphore.release()

    def _upload_callback(self, monitor, upload_progress_bytes, lock, total_bytes, n_files):
        """
        This is the callback/monitor function for the upload threads. It uses
            the byte information to make a progress bar and what not.
            -param int monitor
            -param int upload_progress_bytes
            -param Lock lock
            -param int total_bytes
            -param int n_files
        """
        if upload_progress_bytes.value == -1:
            return
        with lock:
            upload_progress_bytes.value += CHUNK_SIZE  # Chunk size
        if upload_progress_bytes.value == 0:
            progress = 0.0
        else:
            progress = upload_progress_bytes.value / float(total_bytes)
        bar_length = 20
        if progress < 0:
            progress = 0
            status = "Halt...                       \r\n"
        elif progress >= 1:
            progress = 1
            status = "Done.                         \r\n"
            with lock:
                upload_progress_bytes.value = -1
        else:
            status = "Almost done"
        block = int(round(bar_length * progress))
        text = "\rUploading: [{0}] {1:.2f}% {2}".format(
            "#" * block + "-" * (bar_length - block),
            progress * 100, status)

        sys.stderr.write(text)
        sys.stderr.flush()


class ExtendedPotionClient(PotionClient):
    """
    An extention of the PotionClient so we can load extensions
    """
    DATE_FORMAT = "%Y-%m-%d %H:%M"
    SCHEMA_SAVE_DURATION = 1  # day

    def _get_schema(self):
        return self.session \
                   .get(self._schema_url) \
                   .json(cls=PotionJSONSchemaDecoder,
                         referrer=self._schema_url,
                         client=self)

    def _fetch_schema(self, extensions=[], cache_schema=False, creds_file=None):
        log.debug("Fetching API JSON schema.")
        creds_fp = os.path.expanduser('~/.onecodex') if creds_file is None else creds_file

        if cache_schema and os.path.exists(creds_fp):
            creds = json.load(open(creds_fp))

            # Determine if we need to update
            last_update = datetime.datetime.strptime(creds["saved_at"],
                                                     self.DATE_FORMAT)
            time_diff = datetime.datetime.now() - last_update
            schema_update_needed = (time_diff is None or time_diff.days > self.SCHEMA_SAVE_DURATION)

            if schema_update_needed is True:
                schema = None
            else:
                schema = creds.get("schema")

            if schema is None:  # Get and update the schema if it doesn't exist
                schema = self._get_schema()

                # TODO: Implement schema caching with custom PotionEncoder/Decoders
                #       Otherwise, the references don't properly get (de-)serialized
                #
                # creds['saved_at'] = datetime.datetime.strftime(datetime.datetime.now(),
                #                                                self.DATE_FORMAT)
                # creds['schema'] = schema
                # json.dump(creds, open(creds_fp, mode='w'))

        elif cache_schema and not os.path.exists(creds_fp):
            # TODO: Consider saving schema for API key only use in .onecodex file
            schema = self._get_schema()
        else:
            schema = self._get_schema()

        for name, resource_schema in schema['properties'].items():
            class_name = upper_camel_case(name)
            mixin_classes = list(filter(lambda ext_class: class_name in ext_class._extends,
                                        extensions))
            if len(mixin_classes) == 1:
                resource_cls = mixin_classes[0]
                resource = self.resource_factory(name, resource_schema, resource_cls=resource_cls)
            elif len(mixin_classes) > 1:
                log.error("Cannot extend a resource with more than one class: %s", class_name)
                raise ValueError("Resource: %s given more than one extension: %s"
                                 % class_name, str(mixin_classes))
            else:
                resource = self.resource_factory(name, resource_schema)

            setattr(self, class_name, resource)
