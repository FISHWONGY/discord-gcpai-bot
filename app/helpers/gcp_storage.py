from google.cloud import storage
import logging
import json
from os import getenv

GCP_PROJECT = getenv("GCP_PROJECT_ID")

logger = logging.getLogger(__name__)


class GCPStorage:
    def __init__(self) -> None:
        self.client = storage.Client()

    def get_gcs_bucket(self, bucket_name: str) -> storage.Bucket:
        return self.client.bucket(bucket_name)

    @staticmethod
    def create_blob(file_name: str, bucket: storage.Bucket) -> storage.Blob:
        fname = f"{file_name}"
        blob = bucket.blob(fname)
        logger.info("File %s created", fname)
        return blob

    def upload_img(self, file_name: str, bucket: storage.Bucket, data: bytes) -> str:
        blob = self.create_blob(file_name, bucket)
        blob.upload_from_string(data, content_type="image/png")
        blob.make_public()
        logger.info(f"Image url: {blob.public_url}")

        return blob.public_url

    def upload_text(self, file_name: str, bucket: storage.Bucket, data: str):
        blob = self.create_blob(file_name, bucket)
        blob.upload_from_string(data)

    def upload_json(self, file_name: str, bucket: storage.Bucket, data: dict):
        blob = self.create_blob(file_name, bucket)
        message_strings = [json.dumps(message) for message in data]
        flat_data = "\n".join(message_strings)
        blob.upload_from_string(flat_data)

    # bucket = get_bucket("dc-ai-bot")
    # upload("bot-history", {file_name},bucket, data)
