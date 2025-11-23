from storages.backends.s3boto3 import S3Boto3Storage

class PipelineStorage(S3Boto3Storage):
    bucket_name = 'pipelines'
    custom_domain = None
