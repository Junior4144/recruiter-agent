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

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

INPUT_PATH = "data/video_list.json"
OUTPUT_DIR = "data/transcripts"


def fetch_transcript(video_id: str):
    """Returns (full_text, segments) or (None, None) if unavailable."""
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
    except (NoTranscriptFound, TranscriptsDisabled, VideoUnavailable) as e:
        print(f"  ⚠️  No transcript available for {video_id}: {type(e).__name__}")
        return None, None
    except Exception as e:
        print(f"  ⚠️  Unexpected error for {video_id}: {e}")
        return None, None

    full_text = " ".join(seg["text"] for seg in transcript)
    return full_text, transcript


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


if __name__ == "__main__":
    with open(INPUT_PATH, encoding="utf-8") as f:
        videos = json.load(f)

    fetched, skipped = 0, 0
    for v in videos:
        print(f"Fetching: {v['title']}")
        text, segments = fetch_transcript(v["video_id"])
        if text:
            save_transcript(v, text, segments)
            fetched += 1
        else:
            skipped += 1

    print(f"\nDone. Fetched {fetched} transcripts, skipped {skipped} (no captions available).")
