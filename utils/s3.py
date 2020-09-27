import boto3


class S3(object):
    def __init__(self, access_key, secret_key):
        self.client = boto3.client('s3', aws_access_key_id=access_key,
                                   aws_secret_access_key=secret_key)

    def download_file(self, file_path, bucket, object_name):
        with open(file_path, 'wb') as f:
            self.client.download_fileobj(bucket, object_name, f)
