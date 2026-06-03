from job_pilot.api.health import health_check


def test_health_check() -> None:
    result = health_check()

    assert result["status"] == "ok"
