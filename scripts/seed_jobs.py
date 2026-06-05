"""Seed sample job data.

This is a placeholder script for the future ingestion pipeline.
MVP can use data/sample/jobs.json as system-level sample data.
"""

from __future__ import annotations

import json
from pathlib import Path

SAMPLE_FILE = Path(__file__).resolve().parents[1] / "data" / "sample" / "jobs.json"


def main() -> None:
    jobs = json.loads(SAMPLE_FILE.read_text(encoding="utf-8"))
    print(f"Loaded {len(jobs)} sample jobs from {SAMPLE_FILE}")
    print("TODO: implement ingestion service after job_posts/job_skills models are ready.")


if __name__ == "__main__":
    main()
