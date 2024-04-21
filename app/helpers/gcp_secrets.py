from google.cloud import secretmanager
from os import getenv

GCP_PROJECT = getenv("GCP_PROJECT_ID")


class GCPSecrets:
    def __init__(self) -> None:
        self.client = secretmanager.SecretManagerServiceClient()
        self.base_url = f"projects/{GCP_PROJECT}/secrets"

    def get_secret(self, secret):
        secret_response = self.client.access_secret_version(
            name=f"{self.base_url}/{secret}/versions/latest"
        )
        creds = secret_response.payload.data.decode("UTF-8")
        return creds
