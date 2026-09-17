import httpx

from streamgrab.project_update import _version_key, check_project_update


def test_version_key():
    assert _version_key("v1.2.3") == (1, 2, 3)
    assert _version_key("1.2") == (1, 2, 0)


def test_project_update_detects_newer(monkeypatch):
    response = httpx.Response(200, text='[project]\nversion = "0.6.0"\n', request=httpx.Request("GET", "https://example.test"))
    monkeypatch.setattr("streamgrab.project_update.httpx.get", lambda *args, **kwargs: response)
    result = check_project_update("0.5.0")
    assert result is not None
    assert result.latest == "0.6.0"


def test_project_update_failure_does_not_block(monkeypatch):
    def fail(*args, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr("streamgrab.project_update.httpx.get", fail)
    assert check_project_update("0.5.0") is None
