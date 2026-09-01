from __future__ import annotations

import hashlib

from .text import clean_text


def build_job_fingerprint(
    *,
    source_platform: str,
    external_job_id: str | None,
    source_url: str | None,
    title: str | None = None,
    locations: str | None,
) -> str:
    """生成规范化岗位去重指纹。

    优先级：来源稳定 ID > 来源详情 URL > 内容兜底。
    """

    normalized_external_job_id = clean_text(external_job_id)
    normalized_source_url = clean_text(source_url)
    if normalized_external_job_id:
        fingerprint_parts = ("source_id", source_platform, normalized_external_job_id)
    elif normalized_source_url:
        fingerprint_parts = ("source_url", source_platform, normalized_source_url)
    else:
        fingerprint_parts = (
            "content",
            source_platform,
            (title or "").casefold(),
            (locations or "").casefold(),
        )

    raw_fingerprint = "|".join(fingerprint_parts)
    return hashlib.sha256(raw_fingerprint.encode("utf-8")).hexdigest()
