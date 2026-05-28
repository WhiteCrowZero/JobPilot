from job_pilot.api.v1.endpoints.health import health_check


def test_health_check() -> None:
    result = health_check()

    assert result["status"] == "ok"
