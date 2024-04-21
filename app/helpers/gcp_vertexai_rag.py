import os
import textwrap

import time
from typing import List
import vertexai

from langchain.chains import RetrievalQA
from langchain_community.embeddings import VertexAIEmbeddings
from langchain_google_vertexai import VertexAI
from langchain.prompts import PromptTemplate

from utils.matching_engine import MatchingEngine
from utils.matching_engine_utils import MatchingEngineUtils

from helpers.prompts import Prompts
from helpers.gcp_ai import GCPAI


prompt = Prompts()
gcpaiapi = GCPAI()


class CustomVertexAIEmbeddings(VertexAIEmbeddings):
    requests_per_minute: int
    num_instances_per_batch: int

    @staticmethod
    def rate_limit(max_per_minute):
        period = 60 / max_per_minute
        print("Waiting")
        while True:
            before = time.time()
            yield
            after = time.time()
            elapsed = after - before
            sleep_time = max(0, period - elapsed)
            if sleep_time > 0:
                print(".", end="")
                time.sleep(sleep_time)

    def embed_documents(
        self, texts: List[str], batch_size: int = 0
    ) -> List[List[float]]:
        limiter = self.rate_limit(self.requests_per_minute)
        results = []
        docs = list(texts)

        while docs:
            head, docs = (
                docs[: self.num_instances_per_batch],
                docs[self.num_instances_per_batch :],
            )
            chunk = self.client.get_embeddings(head)
            results.extend(chunk)
            next(limiter)

        return [r.values for r in results]


class QuestionAnsweringSystem:
    def __init__(self):
        self.PROJECT_ID = "gcp-prj-123"
        self.REGION = "us-central1"
        self.ME_REGION = "us-central1"
        self.ME_INDEX_NAME = f"{self.PROJECT_ID}-me-index"
        self.ME_EMBEDDING_DIR = f"{self.PROJECT_ID}-me-bucket"
        self.EMBEDDING_QPM = 100
        self.EMBEDDING_NUM_BATCH = 5
        self.NUMBER_OF_RESULTS = 1
        self.SEARCH_DISTANCE_THRESHOLD = 0.6
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "creds/creds.json"

        vertexai.init(project=self.PROJECT_ID, location=self.REGION)

        self.embeddings = CustomVertexAIEmbeddings(
            model_name="textembedding-gecko@001",
            requests_per_minute=self.EMBEDDING_QPM,
            num_instances_per_batch=self.EMBEDDING_NUM_BATCH,
        )

        self.mengine = MatchingEngineUtils(
            self.PROJECT_ID, self.ME_REGION, self.ME_INDEX_NAME
        )

        (
            self.ME_INDEX_ID,
            self.ME_INDEX_ENDPOINT_ID,
        ) = self.mengine.get_index_and_endpoint()

        self.llm = VertexAI(
            model_name="gemini-pro",
            max_output_tokens=8100,
        )

        self.me = MatchingEngine.from_components(
            project_id=self.PROJECT_ID,
            region=self.ME_REGION,
            gcs_bucket_name=f"gs://{self.ME_EMBEDDING_DIR}".split("/")[2],
            embedding=self.embeddings,
            index_id=self.ME_INDEX_ID,
            endpoint_id=self.ME_INDEX_ENDPOINT_ID,
            credentials_path="creds/creds.json",
        )

        self.retriever = self.me.as_retriever(
            search_type="similarity",
            search_kwargs={
                "k": self.NUMBER_OF_RESULTS,
                "search_distance": self.SEARCH_DISTANCE_THRESHOLD,
            },
        )

        self.qa = RetrievalQA.from_chain_type(
            llm=self.llm,
            chain_type="stuff",
            retriever=self.retriever,
            return_source_documents=True,
            verbose=True,
            chain_type_kwargs={
                "prompt": PromptTemplate(
                    template=prompt.RAG_PROMPT,
                    input_variables=["context", "question"],
                ),
            },
        )

        self.qa.combine_documents_chain.verbose = True
        self.qa.combine_documents_chain.llm_chain.verbose = True
        self.qa.combine_documents_chain.llm_chain.llm.verbose = True

        self.rag_nores_list = ["apologize", "unable", "not", "no"]

    @staticmethod
    def wrap(s) -> str:
        return "\n".join(textwrap.wrap(s, width=120, break_long_words=False))

    def formatter(self, result) -> str:
        output = [f"Query: {result['query']}", "." * 80]
        if "source_documents" in result.keys():
            for idx, ref in enumerate(result["source_documents"]):
                output += ["-" * 80, f"REFERENCE #{idx}", "-" * 80]
                if "score" in ref.metadata:
                    output.append(f"Matching Score: {ref.metadata['score']}")
                if "source" in ref.metadata:
                    output.append(f"Document Source: {ref.metadata['source']}")
                if "document_name" in ref.metadata:
                    output.append(f"Document Name: {ref.metadata['document_name']}")
                output += ["." * 80, f"Content: \n{self.wrap(ref.page_content)}"]
        output += ["." * 80, f"Response: {self.wrap(result['result'])}", "." * 80]
        return "\n  \n".join(output)

    def ask(self, query, k=None, search_distance=None) -> str:
        if k is None:
            k = self.NUMBER_OF_RESULTS
        if search_distance is None:
            search_distance = self.SEARCH_DISTANCE_THRESHOLD
        self.qa.retriever.search_kwargs["search_distance"] = search_distance
        self.qa.retriever.search_kwargs["k"] = k
        result = self.qa.invoke({"query": query})
        output_result = self.formatter(result)
        if any(word in result["result"].split() for word in self.rag_nores_list):
            result = gcpaiapi.get_response(
                query, response_type="gem", use_existing_session=False
            )
            output_result = (
                f"The provided context does not contain information about the question, retrieving answer directly from Gemini."
                f"\n\n**Gemini Response:**"
                f"\n{result}"
            )
        return output_result
