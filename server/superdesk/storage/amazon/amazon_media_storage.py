# -*- coding: utf-8; -*-
#
# This file is part of Superdesk.
#
# Copyright 2013, 2014 Sourcefabric z.u. and contributors.
#
# For the full copyright and license information, please see the
# AUTHORS and LICENSE files distributed with this source code, or
# at https://www.sourcefabric.org/superdesk/license

''' Amazon media storage module'''
from eve.io.media import MediaStorage
import tinys3
from superdesk.errors import SuperdeskApiError
import logging
import json
from io import BytesIO
import unittest

logger = logging.getLogger(__name__)


class AmazonObjectWrapper(BytesIO):

    def __init__(self, stream_generator, content_type, length, name, metadata):
        super().__init__()
        for bytes in stream_generator:
            self.write(bytes)
        self.seek(0)
        self.content_type = content_type
        self.length = int(length)
        self.name = name
        self.metadata = metadata


class AmazonMediaStorage(MediaStorage):

    def __init__(self, app=None):
        super().__init__(app)
        username, api_key, endpoint = self.read_from_config()
        self.endpoint = endpoint
        self.conn = tinys3.Connection(username, api_key, tls=True, endpoint=endpoint)
        self.user_metadata_header = 'x-amz-meta-'

    def url_for_media(self, media_id):
        protocol = 'https' if self.app.config.get('S3_USE_HTTPS', False) else 'http'
        return '%s://%s.%s/%s' % (protocol, self.container_name, self.endpoint, media_id)

    def read_from_config(self):
        region = self.app.config.get('AMAZON_REGION', 'us-east-1') or 'us-east-1'
        username = self.app.config['AMAZON_ACCESS_KEY_ID']
        api_key = self.app.config['AMAZON_SECRET_ACCESS_KEY']
        self.container_name = self.app.config['AMAZON_CONTAINER_NAME']
        endpoint = 's3-%s.amazonaws.com' % region
        return username, api_key, endpoint

    def get_bucket_objects(self, marker=None, bucket=None):
        '''
        Fetch the objects available in the specified bucket.
        '''
        bucket = bucket or self.container_name
        params = {'marker': marker}
        rv = self.conn.get_bucket_objects(bucket=bucket, extra_params=params)
        if rv.status_code not in (200, 201):
            message = 'Retrieving the list of files from bucket %s failed' % bucket
            raise SuperdeskApiError.internalError(message)
        content = rv.content.decode('UTF-8')
        return content

    def get(self, id_or_filename):
        """ Opens the file given by name or unique id. Note that although the
        returned file is guaranteed to be a File object, it might actually be
        some subclass. Returns None if no file was found.
        """
        id_or_filename = str(id_or_filename)
        found, obj = self._check_exists(id_or_filename)
        if found:
            metadata = self.extract_metadata_from_headers(obj.headers)
            return AmazonObjectWrapper(obj, obj.headers['content-type'], obj.headers['content-length'], id_or_filename,
                                       metadata)
        return None

    def extract_metadata_from_headers(self, request_headers):
        headers = {}
        for key, value in request_headers.items():
            if self.user_metadata_header in key:
                new_key = key.split(self.user_metadata_header)[1]
                if(value):
                    try:
                        headers[new_key] = json.loads(value)
                    except Exception as ex:
                        logger.exception(ex)
        return headers

    def update_metadata(self, key, metadata):
        if not metadata:
            return
        metadata = self.transform_metadata_to_amazon_format(metadata)
        res = self.conn.update_metadata(key, metadata, bucket=self.container_name)
        if res.status_code not in (200, 201):
            payload = 'Updating metadata for file %s failed' % key
            raise SuperdeskApiError.internalError(payload=payload)

    def transform_metadata_to_amazon_format(self, metadata):
        if not metadata:
            return {}
        file_metadata = {}
        for key, value in metadata.items():
            new_key = self.user_metadata_header + key
            file_metadata[new_key] = value
        return file_metadata

    def put(self, content, filename=None, content_type=None, metadata=None):
        """ Saves a new file using the storage system, preferably with the name
        specified. If there already exists a file with this name name, the
        storage system may modify the filename as necessary to get a unique
        name. Depending on the storage system, a unique id or the actual name
        of the stored file will be returned. The content type argument is used
        to appropriately identify the file when it is retrieved.
        """
        logger.debug('Going to save media file with %s ' % filename)
        found, existing_file = self._check_exists(filename, raise_error=False)
        if found:
            return filename

        try:
            file_metadata = self.transform_metadata_to_amazon_format(metadata)
            res = self.conn.upload(filename, content, self.container_name, content_type=content_type,
                                   headers=file_metadata)
            if res.status_code not in (200, 201):
                raise SuperdeskApiError.internalError('Uploading file to amazon S3 failed')
            return filename
        except Exception as ex:
            logger.exception(ex)
            raise

    def delete(self, id_or_filename):
        id_or_filename = str(id_or_filename)
        del_res = self.conn.delete(id_or_filename, self.container_name)
        logger.debug('Amazon S3 file deleted %s with status' % id_or_filename, del_res.status_code)

    def exists(self, id_or_filename):
        """ Returns True if a file referenced by the given name or unique id
        already exists in the storage system, or False if the name is available
        for a new file.
        """
        id_or_filename = str(id_or_filename)
        found, _ = self._check_exists(id_or_filename)
        return found

    def _check_exists(self, id_or_filename, raise_error=True):
        try:
            obj = self.conn.get(id_or_filename, self.container_name)
            if obj.status_code not in (200, 201) and raise_error:
                message = 'Retrieving file %s from amazon failed' % id_or_filename
                raise SuperdeskApiError.internalError(message)
            return (True, obj)
        except Exception as ex:
            if raise_error:
                logger.exception(ex)
            # File not found
            return (False, None)


class AmazonMediaStorageTestCase(unittest.TestCase):

    def test_url_for_media(self):
        import settings
        # create a dummy app containing only the settings
        app = type('MyObject', (object,), {})
        setattr(app, 'config', settings.__dict__)
        media_id = '123'
        # set s3 settings and test the output
        app.config['AMAZON_CONTAINER_NAME'] = 'AMAZON_CONTAINER_NAME'
        app.config['S3_USE_HTTPS'] = True
        self.assertEquals(AmazonMediaStorage(app).url_for_media(media_id),
                          'https://AMAZON_CONTAINER_NAME.s3.amazonaws.com/%s' % (media_id))
        app.config['S3_USE_HTTPS'] = False
        self.assertEquals(AmazonMediaStorage(app).url_for_media(media_id),
                          'http://AMAZON_CONTAINER_NAME.s3.amazonaws.com/%s' % (media_id))
        app.config['AMAZON_REGION'] = 'AMAZON_REGION'
        self.assertEquals(AmazonMediaStorage(app).url_for_media(media_id),
                          'http://AMAZON_CONTAINER_NAME.AMAZON_REGION.amazonaws.com/%s' % (media_id))
