"""
Switch this GCP project's RAG Engine to Serverless mode.

Why this exists as a separate script:
    As of google-cloud-aiplatform 1.158.0, the Python SDK does not yet expose
    "Serverless mode" (it only knows about Spanner-mode tiers: Basic, Scaled,
    Unprovisioned). The underlying REST API already supports Serverless mode,
    so we call it directly here using the access token from your local
    `gcloud` auth, rather than waiting for the SDK to catch up.

Usage:
    python ingestion/enable_serverless_mode.py

Reads from .env:
    GCP_PROJECT_ID
    GCP_LOCATION
"""

import os
import subprocess

import requests
from dotenv import load_dotenv

load_dotenv()

PROJECT_ID = os.environ["GCP_PROJECT_ID"]
LOCATION = os.environ.get("GCP_LOCATION", "us-central1")


def get_access_token() -> str:
    result = subprocess.run(
        ["gcloud", "auth", "print-access-token"],
        capture_output=True,
        text=True,
        check=True,
        shell=True,  # needed on Windows for gcloud.cmd to resolve correctly
    )
    return result.stdout.strip()


def switch_to_serverless():
    token = get_access_token()
    url = (
        f"https://{LOCATION}-aiplatform.googleapis.com/v1beta1/"
        f"projects/{PROJECT_ID}/locations/{LOCATION}/ragEngineConfig"
    )
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
    payload = {"ragManagedDbConfig": {"serverless": {}}}

    response = requests.patch(url, headers=headers, json=payload)
    print(f"Status: {response.status_code}")
    print(response.text)
    response.raise_for_status()


if __name__ == "__main__":
    switch_to_serverless()
    print("\nRAG Engine switched to Serverless mode.")