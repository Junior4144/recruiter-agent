"""
Create a Vertex AI RAG corpus and import the chunked transcript files from GCS.

Usage:
    python ingestion/setup_rag_corpus.py

Requires:
    pip install google-cloud-aiplatform
    gcloud auth application-default login
    A GCS bucket already populated with your chunk .txt files
        (see ingestion/chunk_transcripts.py + `gsutil -m cp` step)

Reads config from .env:
    GCP_PROJECT_ID
    GCP_LOCATION            (e.g. us-central1)
    GCS_CHUNKS_PATH         (e.g. gs://your-bucket-name/chunks/)
"""

import os

import vertexai
from dotenv import load_dotenv
from vertexai import rag

load_dotenv()

PROJECT_ID = os.environ["GCP_PROJECT_ID"]
LOCATION = os.environ.get("GCP_LOCATION", "us-central1")
GCS_PATH = os.environ["GCS_CHUNKS_PATH"]
CORPUS_DISPLAY_NAME = "recruiter_transcripts"


def get_or_create_corpus():
    vertexai.init(project=PROJECT_ID, location=LOCATION)

    # Avoid creating a duplicate corpus if we've already run this before
    existing = rag.list_corpora()
    for corpus in existing:
        if corpus.display_name == CORPUS_DISPLAY_NAME:
            print(f"Found existing corpus: {corpus.name}")
            return corpus

    backend_config = rag.RagVectorDbConfig(
        rag_embedding_model_config=rag.RagEmbeddingModelConfig(
            vertex_prediction_endpoint=rag.VertexPredictionEndpoint(
                publisher_model="publishers/google/models/text-embedding-005"
            )
        )
    )

    corpus = rag.create_corpus(
        display_name=CORPUS_DISPLAY_NAME,
        description="Chunked transcripts from the recruiter's YouTube resume-review videos",
        backend_config=backend_config,
    )
    print(f"Created new corpus: {corpus.name}")
    return corpus


def import_chunks(corpus):
    print(f"Importing files from {GCS_PATH} ...")

    # These control Vertex's OWN internal re-chunking of whatever it ingests.
    # Since our .txt files are already pre-chunked to the size we want,
    # set chunk_size generously so Vertex treats each file as roughly one
    # chunk rather than re-splitting it further.
    transformation_config = rag.TransformationConfig(
        chunking_config=rag.ChunkingConfig(chunk_size=2500, chunk_overlap=0)
    )

    # Capture per-file failure details so we can see WHY files failed,
    # instead of just getting a bare count back.
    failures_path = f"{GCS_PATH.rstrip('/')}/_import_failures/"

    response = rag.import_files(
        corpus_name=corpus.name,
        paths=[GCS_PATH],
        transformation_config=transformation_config,
        partial_failures_sink=failures_path,
    )
    print(f"Import complete: {response}")
    print(f"\nFailure details (if any) written to: {failures_path}")
    print("Run this to inspect them:")
    print(f'  gsutil cat "{failures_path}*"')


if __name__ == "__main__":
    corpus = get_or_create_corpus()
    import_chunks(corpus)
    print(f"\nCorpus resource name (save this for your agent.py):\n{corpus.name}")