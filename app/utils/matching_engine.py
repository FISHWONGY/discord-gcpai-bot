from __future__ import annotations
import os
import logging
import uuid
from typing import Any, Iterable, List, Optional, Type

import requests
import json

from langchain.docstore.document import Document
from langchain_community.embeddings import TensorflowHubEmbeddings
from langchain.embeddings.base import Embeddings
from langchain.vectorstores.base import VectorStore

from google.cloud import storage
from google.cloud.aiplatform import MatchingEngineIndex, MatchingEngineIndexEndpoint
from google.cloud import aiplatform
from google.cloud import aiplatform_v1
from google.oauth2 import service_account
from google.oauth2.service_account import Credentials
import google.auth
import google.auth.transport.requests

logger = logging.getLogger()


class MatchingEngine(VectorStore):
    def __init__(
        self,
        project_id: str,
        region: str,
        index: MatchingEngineIndex,
        endpoint: MatchingEngineIndexEndpoint,
        embedding: Embeddings,
        gcs_client: storage.Client,
        index_client: aiplatform_v1.IndexServiceClient,
        index_endpoint_client: aiplatform_v1.IndexEndpointServiceClient,
        gcs_bucket_name: str,
        credentials: Credentials,
    ):
        super().__init__()
        self._validate_google_libraries_installation()

        self.project_id = project_id
        self.region = region
        self.index = index
        self.endpoint = endpoint
        self.embedding = embedding
        self.gcs_client = gcs_client
        self.index_client = index_client
        self.index_endpoint_client = index_endpoint_client
        self.gcs_client = gcs_client
        self.key_path = "creds/creds.json"
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.key_path
        self.SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]
        self.creds = service_account.Credentials.from_service_account_file(
            self.key_path,
            scopes=self.SCOPES,
        )
        self.credentials = self.creds
        self.gcs_bucket_name = gcs_bucket_name

    def _validate_google_libraries_installation(self) -> None:
        """Validates that Google libraries that are needed are installed."""
        try:
            from google.cloud import aiplatform, storage  # noqa: F401
            from google.oauth2 import service_account  # noqa: F401
        except ImportError:
            raise ImportError(
                "You must run `pip install --upgrade "
                "google-cloud-aiplatform google-cloud-storage`"
                "to use the MatchingEngine Vectorstore."
            )

    def add_texts(
        self,
        texts: Iterable[str],
        metadatas: Optional[List[dict]] = None,
        **kwargs: Any,
    ) -> List[str]:
        logger.debug("Embedding documents.")
        embeddings = self.embedding.embed_documents(list(texts))
        insert_datapoints_payload = []
        ids = []

        # Streaming index update
        for idx, (embedding, text, metadata) in enumerate(
            zip(embeddings, texts, metadatas)
        ):
            id = uuid.uuid4()
            ids.append(id)
            self._upload_to_gcs(text, f"documents/{id}")
            metadatas[idx]
            insert_datapoints_payload.append(
                aiplatform_v1.IndexDatapoint(
                    datapoint_id=str(id),
                    feature_vector=embedding,
                    restricts=metadata if metadata else [],
                )
            )
            if idx % 100 == 0:
                upsert_request = aiplatform_v1.UpsertDatapointsRequest(
                    index=self.index.name, datapoints=insert_datapoints_payload
                )
                response = self.index_client.upsert_datapoints(request=upsert_request)
                insert_datapoints_payload = []
        if len(insert_datapoints_payload) > 0:
            upsert_request = aiplatform_av1.UpsertDatapointsRequest(
                index=self.index.name, datapoints=insert_datapoints_payload
            )
            _ = self.index_client.upsert_datapoints(request=upsert_request)

        logger.debug("Updated index with new configuration.")
        logger.info(f"Indexed {len(ids)} documents to Matching Engine.")

        return ids

    def _upload_to_gcs(self, data: str, gcs_location: str) -> None:
        bucket = self.gcs_client.get_bucket(self.gcs_bucket_name)
        blob = bucket.blob(gcs_location)
        blob.upload_from_string(data)

    def get_matches(
        self,
        embeddings: List[str],
        n_matches: int,
        index_endpoint: MatchingEngineIndexEndpoint,
    ) -> str:
        request_data = {
            "deployed_index_id": index_endpoint.deployed_indexes[0].id,
            "return_full_datapoint": True,
            "queries": [
                {
                    "datapoint": {"datapoint_id": f"{i}", "feature_vector": emb},
                    "neighbor_count": n_matches,
                }
                for i, emb in enumerate(embeddings)
            ],
        }

        endpoint_address = self.endpoint.public_endpoint_domain_name
        rpc_address = f"https://{endpoint_address}/v1beta1/{index_endpoint.resource_name}:findNeighbors"
        endpoint_json_data = json.dumps(request_data)

        logger.debug(f"Querying Matching Engine Index Endpoint {rpc_address}")

        request = google.auth.transport.requests.Request()
        self.credentials.refresh(request)
        header = {"Authorization": "Bearer " + self.credentials.token}

        return requests.post(rpc_address, data=endpoint_json_data, headers=header)

    def similarity_search(
        self, query: str, k: int = 4, search_distance: float = 0.65, **kwargs: Any
    ) -> List[Document]:
        logger.debug(f"Embedding query {query}.")
        embedding_query = self.embedding.embed_documents([query])
        deployed_index_id = self._get_index_id()
        logger.debug(f"Deployed Index ID = {deployed_index_id}")

        # TO-DO: Pending query sdk integration
        # response = self.endpoint.match(
        #     deployed_index_id=self._get_index_id(),
        #     queries=embedding_query,
        #     num_neighbors=k,
        # )

        response = self.get_matches(embedding_query, k, self.endpoint)

        if response.status_code == 200:
            response = response.json()["nearestNeighbors"]
        else:
            raise Exception(f"Failed to query index {str(response)}")

        if len(response) == 0:
            return []

        logger.debug(f"Found {len(response)} matches for the query {query}.")

        results = []

        # Only getting the first one because queries receives an array
        # and the similarity_search method only recevies one query. This
        # means that the match method will always return an array with only
        # one element.
        for doc in response[0]["neighbors"]:
            page_content = self._download_from_gcs(
                f"documents/{doc['datapoint']['datapointId']}"
            )
            metadata = {}
            if "restricts" in doc["datapoint"]:
                metadata = {
                    item["namespace"]: item["allowList"][0]
                    for item in doc["datapoint"]["restricts"]
                }
            if "distance" in doc:
                metadata["score"] = doc["distance"]
                if doc["distance"] >= search_distance:
                    results.append(
                        Document(page_content=page_content, metadata=metadata)
                    )
            else:
                results.append(Document(page_content=page_content, metadata=metadata))

        logger.debug("Downloaded documents for query.")

        return results

    def _get_index_id(self) -> str:
        for index in self.endpoint.deployed_indexes:
            if index.index == self.index.name:
                return index.id

        raise ValueError(
            f"No index with id {self.index.name} "
            f"deployed on enpoint "
            f"{self.endpoint.display_name}."
        )

    def _download_from_gcs(self, gcs_location: str) -> str:
        bucket = self.gcs_client.get_bucket(self.gcs_bucket_name)
        try:
            blob = bucket.blob(gcs_location)
            return blob.download_as_string()
        except Exception as e:
            logger.error(f"Failed to download {gcs_location} from GCS: {e}")
            return ""

    @classmethod
    def from_texts(
        cls: Type["MatchingEngine"],
        texts: List[str],
        embedding: Embeddings,
        metadatas: Optional[List[dict]] = None,
        **kwargs: Any,
    ) -> "MatchingEngine":
        """Use from components instead."""
        raise NotImplementedError(
            "This method is not implemented. Instead, you should initialize the class"
            " with `MatchingEngine.from_components(...)` and then call "
            "`from_texts`"
        )

    @classmethod
    def from_documents(
        cls: Type["MatchingEngine"],
        documents: List[str],
        embedding: Embeddings,
        metadatas: Optional[List[dict]] = None,
        **kwargs: Any,
    ) -> "MatchingEngine":
        """Use from components instead."""
        raise NotImplementedError(
            "This method is not implemented. Instead, you should initialize the class"
            " with `MatchingEngine.from_components(...)` and then call "
            "`from_documents`"
        )

    @classmethod
    def from_components(
        cls: Type["MatchingEngine"],
        project_id: str,
        region: str,
        gcs_bucket_name: str,
        index_id: str,
        endpoint_id: str,
        credentials_path: Optional[str] = "creds/creds.json",
        embedding: Optional[Embeddings] = None,
    ) -> "MatchingEngine":
        gcs_bucket_name = cls._validate_gcs_bucket(gcs_bucket_name)

        # Set credentials
        if credentials_path:
            credentials = cls._create_credentials_from_file(credentials_path)
        else:
            credentials, _ = google.auth.default()
            request = google.auth.transport.requests.Request()
            credentials.refresh(request)

        index = cls._create_index_by_id(index_id, region, credentials)
        endpoint = cls._create_endpoint_by_id(
            endpoint_id, project_id, region, credentials
        )

        gcs_client = cls._get_gcs_client(credentials, project_id)
        index_client = cls._get_index_client(region, credentials)
        index_endpoint_client = cls._get_index_endpoint_client(region, credentials)
        cls._init_aiplatform(project_id, region, gcs_bucket_name, credentials)

        return cls(
            project_id=project_id,
            region=region,
            index=index,
            endpoint=endpoint,
            embedding=embedding or cls._get_default_embeddings(),
            gcs_client=gcs_client,
            index_client=index_client,
            index_endpoint_client=index_endpoint_client,
            credentials=credentials,
            gcs_bucket_name=gcs_bucket_name,
        )

    @classmethod
    def _validate_gcs_bucket(cls, gcs_bucket_name: str) -> str:
        gcs_bucket_name = gcs_bucket_name.replace("gs://", "")
        if "/" in gcs_bucket_name:
            raise ValueError(
                f"The argument gcs_bucket_name should only be "
                f"the bucket name. Received {gcs_bucket_name}"
            )
        return gcs_bucket_name

    @classmethod
    def _create_credentials_from_file(
        cls, json_credentials_path: Optional[str]
    ) -> Optional[Credentials]:
        credentials = None
        if json_credentials_path is not None:
            credentials = service_account.Credentials.from_service_account_file(
                json_credentials_path
            )

        return credentials

    @classmethod
    def _create_index_by_id(
        cls, index_id: str, region: str, credentials: "Credentials"
    ) -> "aiplatform_v1.Index":
        logger.debug(f"Creating matching engine index with id {index_id}.")
        index_client = cls._get_index_client(region, credentials)
        request = aiplatform_v1.GetIndexRequest(name=index_id)
        return index_client.get_index(request=request)

    @classmethod
    def _create_endpoint_by_id(
        cls, endpoint_id: str, project_id: str, region: str, credentials: "Credentials"
    ) -> MatchingEngineIndexEndpoint:
        logger.debug(f"Creating endpoint with id {endpoint_id}.")
        return aiplatform.MatchingEngineIndexEndpoint(
            index_endpoint_name=endpoint_id,
            project=project_id,
            location=region,
            credentials=credentials,
        )

    @classmethod
    def _get_gcs_client(
        cls, credentials: "Credentials", project_id: str
    ) -> "storage.Client":
        return storage.Client(credentials=credentials, project=project_id)

    @classmethod
    def _get_index_client(
        cls, region: str, credentials: "Credentials"
    ) -> "aiplatform_v1.IndexServiceClient":
        endpoint = f"{region}-aiplatform.googleapis.com"
        return aiplatform_v1.IndexServiceClient(
            client_options=dict(api_endpoint=endpoint), credentials=credentials
        )

    @classmethod
    def _get_index_endpoint_client(
        cls, region: str, credentials: "Credentials"
    ) -> "aiplatform_v1.IndexEndpointServiceClient":
        endpoint = f"{region}-aiplatform.googleapis.com"
        return aiplatform_v1.IndexEndpointServiceClient(
            client_options=dict(api_endpoint=endpoint), credentials=credentials
        )

    @classmethod
    def _init_aiplatform(
        cls,
        project_id: str,
        region: str,
        gcs_bucket_name: str,
        credentials: "Credentials",
    ) -> None:
        logger.debug(
            f"Initializing AI Platform for project {project_id} on "
            f"{region} and for {gcs_bucket_name}."
        )
        aiplatform.init(
            project=project_id,
            location=region,
            staging_bucket=gcs_bucket_name,
            credentials=credentials,
        )

    @classmethod
    def _get_default_embeddings(cls) -> TensorflowHubEmbeddings:
        """This function returns the default embedding."""
        return TensorflowHubEmbeddings()
