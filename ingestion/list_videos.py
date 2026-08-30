"""
Fetch metadata for all videos uploaded to a YouTube channel in the last year.

Usage:
    python ingestion/list_videos.py

Set CHANNEL_URL below to the channel's /videos page.
Writes results to data/video_list.json
"""

import json
import os
from datetime import datetime, timedelta

import yt_dlp

CHANNEL_URL = "https://www.youtube.com/@HisChannelHandle/videos"  # TODO: update this
DAYS_BACK = 365
OUTPUT_PATH = "data/video_list.json"


def get_recent_videos(channel_url: str, days_back: int = 365) -> list[dict]:
    cutoff = datetime.now() - timedelta(days=days_back)

    # Step 1: get a flat list of video IDs from the channel (fast, no per-video metadata)
    flat_opts = {
        "extract_flat": True,
        "quiet": True,
        "skip_download": True,
    }
    with yt_dlp.YoutubeDL(flat_opts) as ydl:
        info = ydl.extract_info(channel_url, download=False)

    entries = info.get("entries", [])
    print(f"Channel listing returned {len(entries)} videos total. Checking upload dates...")

    videos = []
    detail_opts = {"quiet": True, "skip_download": True}
    with yt_dlp.YoutubeDL(detail_opts) as ydl:
        for i, entry in enumerate(entries):
            video_id = entry.get("id")
            if not video_id:
                continue
            try:
                full_info = ydl.extract_info(
                    f"https://www.youtube.com/watch?v={video_id}", download=False
                )
            except Exception as e:
                print(f"  ⚠️  Skipping {video_id}: {e}")
                continue

            upload_date_str = full_info.get("upload_date")  # format: YYYYMMDD
            if not upload_date_str:
                continue
            upload_date = datetime.strptime(upload_date_str, "%Y%m%d")

            if upload_date >= cutoff:
                videos.append(
                    {
                        "video_id": video_id,
                        "title": full_info.get("title"),
                        "upload_date": upload_date.isoformat(),
                        "url": f"https://www.youtube.com/watch?v={video_id}",
                    }
                )
                print(f"  ✓ [{i+1}/{len(entries)}] {full_info.get('title')} ({upload_date.date()})")
            else:
                # Channel listings are usually newest-first, so once we hit an old
                # video we can stop early instead of checking the whole history.
                print(f"  ⏹ Hit video older than {days_back} days, stopping scan.")
                break

    return videos


if __name__ == "__main__":
    videos = get_recent_videos(CHANNEL_URL, DAYS_BACK)
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(videos, f, ensure_ascii=False, indent=2)

    print(f"\nSaved {len(videos)} videos to {OUTPUT_PATH}")
