"""
Chunk fetched transcripts into retrieval-sized pieces for the RAG corpus.

Usage:
    python ingestion/chunk_transcripts.py

Reads:  data/transcripts/{video_id}.json      (from fetch_transcripts.py)
Writes: data/chunks/{video_id}_chunk_{n}.txt  (one file per chunk, ready to upload to GCS)

Chunking strategy:
    Instead of splitting on a fixed character count (which can cut a sentence
    or thought in half), we walk the timestamped segments and accumulate them
    into a chunk until we hit the target size, then start a new chunk at the
    nearest segment boundary. This keeps each chunk as a coherent stretch of
    speech, and lets us tag every chunk with the timestamp it starts at.
"""

import json
import os

INPUT_DIR = "data/transcripts"
OUTPUT_DIR = "data/chunks"

TARGET_CHARS = 2000   # roughly 400-500 tokens per chunk
OVERLAP_CHARS = 300   # ~15% overlap so context isn't lost at chunk boundaries


def format_timestamp(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def chunk_transcript(transcript: dict) -> list[dict]:
    segments = transcript["segments"]
    chunks = []

    current_text = ""
    current_start = segments[0]["start"] if segments else 0
    i = 0

    while i < len(segments):
        seg = segments[i]
        current_text += (" " if current_text else "") + seg["text"]

        if len(current_text) >= TARGET_CHARS or i == len(segments) - 1:
            chunks.append(
                {
                    "text": current_text.strip(),
                    "start_seconds": current_start,
                }
            )

            if i == len(segments) - 1:
                break

            # Back up by roughly OVERLAP_CHARS worth of segments so the next
            # chunk overlaps with the tail of this one, instead of losing context
            overlap_text = ""
            back = i
            while back > 0 and len(overlap_text) < OVERLAP_CHARS:
                overlap_text = segments[back]["text"] + " " + overlap_text
                back -= 1

            current_text = overlap_text.strip()
            current_start = segments[back + 1]["start"] if back + 1 < len(segments) else seg["start"]

        i += 1

    return chunks


def save_chunks(video_meta: dict, chunks: list[dict]):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for idx, chunk in enumerate(chunks):
        timestamp = format_timestamp(chunk["start_seconds"])
        # Each chunk file is plain text with a small metadata header baked in.
        # Vertex AI RAG's default chunking would otherwise ignore our timestamp
        # boundaries, so we pre-chunk and upload one file per chunk directly.
        header = (
            f"Video: {video_meta['title']}\n"
            f"URL: {video_meta['url']}&t={int(chunk['start_seconds'])}s\n"
            f"Timestamp: {timestamp}\n"
            f"Upload date: {video_meta['upload_date']}\n"
            "---\n"
        )
        content = header + chunk["text"]

        filename = f"{video_meta['video_id']}_chunk_{idx:03d}.txt"
        path = os.path.join(OUTPUT_DIR, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)


if __name__ == "__main__":
    transcript_files = [f for f in os.listdir(INPUT_DIR) if f.endswith(".json")]
    print(f"Found {len(transcript_files)} transcripts to chunk.\n")

    total_chunks = 0
    for fname in transcript_files:
        with open(os.path.join(INPUT_DIR, fname), encoding="utf-8") as f:
            transcript = json.load(f)

        if not transcript.get("segments"):
            print(f"  ⚠️  Skipping {transcript['title']} — no segments found")
            continue

        chunks = chunk_transcript(transcript)
        save_chunks(transcript, chunks)
        total_chunks += len(chunks)
        print(f"  ✓ {transcript['title']} → {len(chunks)} chunks")

    print(f"\nDone. {total_chunks} total chunks written to {OUTPUT_DIR}/")