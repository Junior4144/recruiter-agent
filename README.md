# recruiter-agent

A retrieval-augmented agent that answers resume and hiring questions in the voice of a specific
recruiter — grounded in the transcripts of that recruiter's own YouTube videos rather than in
generic LLM advice.

The repo contains two halves:

1. **An ingestion pipeline** that lists a YouTube channel's recent videos, pulls their captions,
   chunks them on natural speech boundaries, and imports the chunks into a
   [Vertex AI RAG Engine](https://cloud.google.com/vertex-ai/generative-ai/docs/rag-overview) corpus.
2. **An agent** built with the [Google Agent Development Kit (ADK)](https://google.github.io/adk-docs/)
   that queries that corpus before answering, so its opinions trace back to something the recruiter
   actually said on camera.

## How it works

```
YouTube channel
      │  list_videos.py        (yt-dlp)
      ▼
data/video_list.json
      │  fetch_transcripts.py  (youtube-transcript-api)
      ▼
data/transcripts/{video_id}.json      timestamped caption segments
      │  chunk_transcripts.py
      ▼
data/chunks/{video_id}_chunk_NNN.txt  ~2k chars, 300-char overlap, timestamped header
      │  gsutil cp  →  GCS bucket
      │  setup_rag_corpus.py
      ▼
Vertex AI RAG corpus (text-embedding-005)
      │  VertexAiRagRetrieval tool
      ▼
recruiter_agent/agent.py  →  adk web / adk run
```

Two chunking details worth knowing:

- Chunks are cut at **segment boundaries**, not at a fixed character offset, so a chunk is a
  coherent stretch of speech rather than a sentence sliced in half. Each chunk carries a header with
  the video title, upload date, and a deep link (`...&t=1234s`) to the moment it starts.
- Because the files are **pre-chunked**, `setup_rag_corpus.py` deliberately sets Vertex's own
  `chunk_size` high (2500, zero overlap) so it treats each uploaded file as roughly one chunk instead
  of re-splitting the work.

## Repo layout

| Path | Purpose |
| --- | --- |
| [ingestion/list_videos.py](ingestion/list_videos.py) | Scrape channel metadata for videos uploaded in the last N days |
| [ingestion/fetch_transcripts.py](ingestion/fetch_transcripts.py) | Download captions; resumable, rate-limited, logs videos with no captions |
| [ingestion/chunk_transcripts.py](ingestion/chunk_transcripts.py) | Split transcripts into overlapping, timestamped chunk files |
| [ingestion/setup_rag_corpus.py](ingestion/setup_rag_corpus.py) | Create the Vertex RAG corpus and import chunks from GCS |
| [ingestion/enable_serverless_mode.py](ingestion/enable_serverless_mode.py) | One-off REST call to put the project's RAG Engine in Serverless mode |
| [ingestion/debug_rag_version.py](ingestion/debug_rag_version.py) | Prints the installed `aiplatform` version and `rag.import_files` signature |
| [recruiter_agent/agent.py](recruiter_agent/agent.py) | The ADK agent: persona instruction + RAG retrieval tool |

`data/` is generated and git-ignored — transcripts belong to the channel owner and are not
redistributed here. You point the pipeline at a channel and build your own corpus.

## Prerequisites

- Python 3.11+ (developed on 3.13)
- A Google Cloud project with billing enabled, and the
  **Vertex AI** (`aiplatform.googleapis.com`) and **Cloud Storage** APIs enabled
- [`gcloud` CLI](https://cloud.google.com/sdk/docs/install), authenticated
- A GCS bucket to stage the chunk files

## Setup

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

gcloud auth login
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```

Authentication is entirely via Application Default Credentials — there are no API keys or service
account JSON files in this repo, and none are needed.

Then create the two env files from their templates:

```bash
cp .env.example .env                                 # used by the ingestion scripts
cp recruiter_agent/.env.example recruiter_agent/.env # used by the agent (ADK loads this one)
```

| Variable | File | Meaning |
| --- | --- | --- |
| `YT_CHANNEL_URL` | `.env` | The channel's `/videos` page |
| `GCP_PROJECT_ID` | `.env` | Google Cloud project ID |
| `GCP_LOCATION` | `.env` | Vertex region, e.g. `us-central1` |
| `GCS_CHUNKS_PATH` | `.env` | `gs://your-bucket/chunks/` |
| `GOOGLE_GENAI_USE_VERTEXAI` | `recruiter_agent/.env` | `TRUE` — route the model through Vertex, not the Gemini API |
| `GOOGLE_CLOUD_PROJECT` | `recruiter_agent/.env` | Same project ID |
| `GOOGLE_CLOUD_LOCATION` | `recruiter_agent/.env` | Model region |
| `RAG_CORPUS_NAME` | `recruiter_agent/.env` | Full corpus resource name printed by `setup_rag_corpus.py` |

## Building the corpus

Run from the repo root, in order:

```bash
# 1. Enumerate the channel's last year of uploads  →  data/video_list.json
python ingestion/list_videos.py

# 2. Fetch captions  →  data/transcripts/*.json
#    Sleeps 5s between videos and skips anything already on disk, so it is safe
#    to stop and re-run. Videos with captions disabled are recorded in
#    data/no_transcript.json and never retried.
python ingestion/fetch_transcripts.py

# 3. Chunk them  →  data/chunks/*.txt
python ingestion/chunk_transcripts.py

# 4. Stage the chunks in GCS
gsutil -m cp data/chunks/*.txt gs://your-bucket/chunks/

# 5. (once per project) put RAG Engine in Serverless mode
python ingestion/enable_serverless_mode.py

# 6. Create the corpus and import the chunks
python ingestion/setup_rag_corpus.py
```

Step 6 prints the corpus resource name — copy it into `RAG_CORPUS_NAME` in
`recruiter_agent/.env`. `setup_rag_corpus.py` is idempotent: it reuses an existing corpus with the
same display name rather than creating a duplicate. Per-file import failures are written to
`gs://your-bucket/chunks/_import_failures/`; inspect them with `gsutil cat`.

## Running the agent

```bash
adk web          # browser UI, pick "recruiter_agent"
adk run recruiter_agent   # terminal chat
```

The agent is told to call its `recruiter_knowledge` retrieval tool before answering anything about
resumes, hiring, or applications, to match the recruiter's tone, and — importantly — to say it
doesn't have a take rather than fall back on generic advice when retrieval comes up empty. The
retriever returns the top 5 chunks within a 0.6 vector-distance threshold.

## Notes and caveats

- **`enable_serverless_mode.py` exists because of an SDK gap.** As of
  `google-cloud-aiplatform==1.158.0` the Python SDK only exposes Spanner-mode RAG tiers; Serverless
  mode is available over REST only, so the script patches `ragEngineConfig` directly using a
  `gcloud` access token. It shells out with `shell=True` because `gcloud.cmd` needs it on Windows.
- **YouTube rate limiting.** `fetch_transcripts.py` pauses 5 seconds between videos. Lowering that
  risks an IP block; the script's resume behaviour makes a slow run cheap to restart.
- **Cost.** Embedding and RAG Engine storage/queries are billed Vertex AI usage. A few hundred
  videos' worth of chunks is small, but it is not free.
- `requirements.txt` is a pinned full freeze of the working environment, including the ingestion-only
  dependencies (`yt-dlp`, `youtube-transcript-api`).

## License

No license is currently declared, which means default copyright applies. Add a `LICENSE` file if you
intend others to reuse this. Video transcripts fetched by the pipeline remain the property of their
original creators.
