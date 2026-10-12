"""
API contract tests asserting endpoints, request validation, status codes, and response schemas.
All heavy ML stages are mocked to guarantee CPU execution with zero network and zero GPU overhead.
"""
import io
from unittest.mock import patch


def test_api_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["version"] == "4.0"
    assert data["stages"] == 9
    assert data["service"] == "FinGuard"


def test_scan_text_valid(client):
    payload = {"text": "Guaranteed 40% returns on BankNifty jackpot calls. Join Telegram: t.me/vip"}
    res = client.post("/api/scan/text", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["scan_type"] == "text"
    assert "verdict" in data
    assert "is_scam" in data
    assert "composite_risk_score" in data
    assert "domain_scan" in data
    assert "sebi_analysis" in data
    assert "registry_check" in data
    assert "scores_complaint" in data


def test_scan_text_too_short(client):
    res = client.post("/api/scan/text", json={"text": "abc"})
    assert res.status_code == 400
    assert "too short" in res.json()["detail"].lower()


def test_scan_url_valid(client):
    res = client.post("/api/scan/url", json={"url": "https://zerodha.com"})
    assert res.status_code == 200
    data = res.json()
    assert data["scan_type"] == "url"
    assert "url_result" in data
    assert "scores_complaint" in data


def test_scan_url_too_short(client):
    res = client.post("/api/scan/url", json={"url": "a"})
    assert res.status_code == 400
    assert "too short" in res.json()["detail"].lower()


def test_invalid_file_types(client):
    # Video rejects .txt
    fake_file = io.BytesIO(b"dummy text")
    res = client.post("/api/jobs", files={"file": ("test.txt", fake_file, "text/plain")})
    assert res.status_code == 400
    assert "unsupported" in res.json()["detail"].lower()

    # Audio rejects .exe
    fake_file.seek(0)
    res = client.post("/api/scan/audio", files={"file": ("malware.exe", fake_file, "application/octet-stream")})
    assert res.status_code == 400

    # Image rejects .pdf
    fake_file.seek(0)
    res = client.post("/api/scan/image", files={"file": ("document.pdf", fake_file, "application/pdf")})
    assert res.status_code == 400

    # APK rejects .zip
    fake_file.seek(0)
    res = client.post("/api/scan/apk", files={"file": ("app.zip", fake_file, "application/zip")})
    assert res.status_code == 400


def test_job_create_poll_and_complaint(client):
    """Mocks run_pipeline to test asynchronous job queuing, polling, and complaint download."""
    with patch("app.run_pipeline"):
        fake_video = io.BytesIO(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom")
        res = client.post("/api/jobs", files={"file": ("sample.mp4", fake_video, "video/mp4")})
        assert res.status_code == 200
        data = res.json()
        assert "job_id" in data
        assert data["status"] == "queued"
        job_id = data["job_id"]

        # Poll job status
        poll_res = client.get(f"/api/jobs/{job_id}")
        assert poll_res.status_code == 200
        assert poll_res.json()["job_id"] == job_id

        # Non-existent job
        not_found = client.get("/api/jobs/non-existent-uuid-12345")
        assert not_found.status_code == 404

        # Manually populate result in jobs dictionary to test complaint retrieval
        from app import jobs
        jobs[job_id]["result"] = {
            "verdict": "Warning: SEBI Violation / Scam",
            "is_deepfake": False,
            "is_scam": True,
            "composite_risk_score": 0.85,
            "scores_complaint": "SEBI SCORES EVIDENCE DOSSIER\nComplaint text here...",
        }
        complaint_res = client.get(f"/api/jobs/{job_id}/complaint")
        assert complaint_res.status_code == 200
        assert "SEBI SCORES EVIDENCE DOSSIER" in complaint_res.text


def test_oversize_file_rejection(client):
    """Simulates an upload exceeding MAX_UPLOAD_SIZE (100MB)."""
    with patch("app.MAX_UPLOAD_SIZE", 50):  # Mock limit to 50 bytes for test
        oversize_data = io.BytesIO(b"A" * 100)
        res = client.post("/api/jobs", files={"file": ("big.mp4", oversize_data, "video/mp4")})
        assert res.status_code == 413
        assert "exceeds maximum allowed size" in res.json()["detail"].lower()
