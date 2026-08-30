"""
Fetch transcripts for every video listed in data/video_list.json.

Usage:
    python ingestion/fetch_transcripts.py

Requires: pip install youtube-transcript-api
Reads:    data/video_list.json  (produced by list_videos.py)
Writes:   data/transcripts/{video_id}.json  (one file per video)
"""

import json
import os
import time

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

INPUT_PATH = "data/video_list.json"
OUTPUT_DIR = "data/transcripts"
SKIP_LOG_PATH = "data/no_transcript.json"  # video IDs confirmed to have no captions
DELAY_SECONDS = 5  # pause between requests to avoid rate limiting


def fetch_transcript(video_id: str):
    """Returns (full_text, segments) or (None, None) if unavailable."""
    ytt_api = YouTubeTranscriptApi()
    try:
        fetched = ytt_api.fetch(video_id)  # returns a FetchedTranscript object
    except (NoTranscriptFound, TranscriptsDisabled, VideoUnavailable) as e:
        print(f"  ⚠️  No transcript available for {video_id}: {type(e).__name__}")
        return None, None
    except Exception as e:
        print(f"  ⚠️  Unexpected error for {video_id}: {e}")
        return None, None

    # FetchedTranscript is iterable and yields snippet objects with .text/.start/.duration
    segments = [
        {"text": snip.text, "start": snip.start, "duration": snip.duration}
        for snip in fetched
    ]
    full_text = " ".join(seg["text"] for seg in segments)
    return full_text, segments


def save_transcript(video_meta: dict, full_text: str, segments: list):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out = {
        "video_id": video_meta["video_id"],
        "title": video_meta["title"],
        "url": video_meta["url"],
        "upload_date": video_meta["upload_date"],
        "full_text": full_text,
        # Keep timestamped segments around — useful later for:
        #   - chunking by natural speech boundaries instead of raw token windows
        #   - citing back to "around minute X" of a specific video
        "segments": segments,
    }
    path = os.path.join(OUTPUT_DIR, f"{video_meta['video_id']}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)


def load_skip_log() -> set:
    if not os.path.exists(SKIP_LOG_PATH):
        return set()
    with open(SKIP_LOG_PATH, encoding="utf-8") as f:
        return set(json.load(f))


def save_skip_log(skip_ids: set):
    with open(SKIP_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(sorted(skip_ids), f, indent=2)


if __name__ == "__main__":
    with open(INPUT_PATH, encoding="utf-8") as f:
        videos = json.load(f)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Skip anything already successfully fetched, or already confirmed to have no captions
    already_done = {
        fname.removesuffix(".json") for fname in os.listdir(OUTPUT_DIR) if fname.endswith(".json")
    }
    no_transcript_ids = load_skip_log()
    remaining = [
        v for v in videos
        if v["video_id"] not in already_done and v["video_id"] not in no_transcript_ids
    ]

    print(
        f"{len(videos)} total videos | {len(already_done)} already fetched | "
        f"{len(no_transcript_ids)} known to have no captions | {len(remaining)} remaining.\n"
    )

    fetched, skipped = 0, 0
    for i, v in enumerate(remaining):
        print(f"[{i+1}/{len(remaining)}] Fetching: {v['title']}")
        text, segments = fetch_transcript(v["video_id"])
        if text:
            save_transcript(v, text, segments)
            fetched += 1
        else:
            skipped += 1
            no_transcript_ids.add(v["video_id"])
            save_skip_log(no_transcript_ids)  # persist immediately, don't lose progress on crash

        # Be polite to YouTube's servers — avoid getting IP-blocked for bursty requests
        if i < len(remaining) - 1:
            time.sleep(DELAY_SECONDS)

    print(f"\nDone this run. Fetched {fetched}, skipped {skipped} (no captions available).")
    print(f"Total transcripts on disk now: {len(already_done) + fetched}")