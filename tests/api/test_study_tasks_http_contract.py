from __future__ import annotations

from uuid import uuid4

import httpx
import pytest
from fastapi.routing import APIRoute

from job_pilot.modules.study_tasks.router import router as study_tasks_router
from tests.api.endpoints import (
    AUTH_REGISTER_EMAIL_ENDPOINT,
    STUDY_TASKS_ENDPOINT,
    study_task_endpoint,
    study_task_generate_from_target_endpoint,
    study_task_question_attempts_endpoint,
    study_task_question_skip_endpoint,
)


async def register_study_task_user_headers(
    api_client: httpx.AsyncClient,
    *,
    prefix: str,
) -> dict[str, str]:
    """注册学习任务接口测试用户并返回 bearer token 请求头。"""

    register_response = await api_client.post(
        AUTH_REGISTER_EMAIL_ENDPOINT,
        json={
            "email": f"{prefix}-{uuid4().hex}@example.com",
            "password": "Password123",
            "display_name": "Study Task User",
        },
    )
    access_token = register_response.json()["access_token"]
    return {"Authorization": f"Bearer {access_token}"}


@pytest.mark.parametrize(
    ("method", "endpoint"),
    [
        ("GET", STUDY_TASKS_ENDPOINT),
        ("POST", STUDY_TASKS_ENDPOINT),
        ("POST", study_task_generate_from_target_endpoint(1)),
        ("PATCH", study_task_endpoint(1)),
        ("POST", study_task_question_attempts_endpoint(1, 1)),
        ("POST", study_task_question_skip_endpoint(1, 1)),
    ],
)
@pytest.mark.asyncio
async def test_study_task_http_requires_bearer_token(
    api_client: httpx.AsyncClient,
    method: str,
    endpoint: str,
) -> None:
    """学习任务 HTTP 端点必须校验当前用户身份。"""

    response = await api_client.request(method, endpoint, json={})

    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_list_study_tasks_parses_repeated_query_params(
    api_client: httpx.AsyncClient,
) -> None:
    """学习任务列表 HTTP 层支持 repeated query list 参数。"""

    headers = await register_study_task_user_headers(api_client, prefix="study-list")

    response = await api_client.get(
        STUDY_TASKS_ENDPOINT,
        params=[
            ("statuses", "todo"),
            ("statuses", "in_progress"),
            ("skill_ids", "1"),
            ("skill_ids", "2"),
            ("page", "1"),
            ("page_size", "5"),
        ],
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["page_size"] == 5


def test_create_study_task_route_declares_created_status() -> None:
    """手动创建学习任务成功时应声明 201 Created。"""

    route = next(
        route
        for route in study_tasks_router.routes
        if isinstance(route, APIRoute) and route.path == "" and "POST" in route.methods
    )

    assert route.status_code == 201


@pytest.mark.asyncio
async def test_create_study_task_rejects_duplicate_question_ids(
    api_client: httpx.AsyncClient,
) -> None:
    """手动创建学习任务不允许重复绑定同一道题。"""

    headers = await register_study_task_user_headers(api_client, prefix="study-create-dup")

    response = await api_client.post(
        STUDY_TASKS_ENDPOINT,
        json={
            "skill_id": 1,
            "title": "Practice Python basics",
            "question_ids": [1, 1],
        },
        headers=headers,
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_generate_study_tasks_from_target_exposes_request_contract(
    api_client: httpx.AsyncClient,
) -> None:
    """生成学习任务接口先固定请求字段和空实现响应。"""

    headers = await register_study_task_user_headers(api_client, prefix="study-generate")

    response = await api_client.post(
        study_task_generate_from_target_endpoint(1),
        json={
            "max_tasks": 2,
            "question_count_per_task": 3,
            "difficulty": "medium",
            "include_weak_skills": True,
            "include_missing_skills": True,
            "due_days": 7,
            "required_level": 3,
        },
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "created_count": 0,
        "reused_count": 0,
        "skipped_skill_count": 0,
        "skipped_items": [],
    }


@pytest.mark.asyncio
async def test_generate_study_tasks_rejects_empty_gap_scope(
    api_client: httpx.AsyncClient,
) -> None:
    """生成学习任务必须至少选择一种缺口类型。"""

    headers = await register_study_task_user_headers(api_client, prefix="study-gap-scope")

    response = await api_client.post(
        study_task_generate_from_target_endpoint(1),
        json={
            "include_weak_skills": False,
            "include_missing_skills": False,
        },
        headers=headers,
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_submit_attempt_rejects_duplicate_selected_option_ids(
    api_client: httpx.AsyncClient,
) -> None:
    """作答请求不允许重复提交同一个选项 ID。"""

    headers = await register_study_task_user_headers(api_client, prefix="study-attempt-dup")

    response = await api_client.post(
        study_task_question_attempts_endpoint(1, 1),
        json={"selected_option_ids": [1, 1]},
        headers=headers,
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_submit_attempt_rejects_mixed_answer_payload(
    api_client: httpx.AsyncClient,
) -> None:
    """作答请求不允许同时提交选项和开放文本。"""

    headers = await register_study_task_user_headers(api_client, prefix="study-attempt-mixed")

    response = await api_client.post(
        study_task_question_attempts_endpoint(1, 1),
        json={"selected_option_ids": [1], "answer_text": "mixed payload"},
        headers=headers,
    )

    assert response.status_code == 422
