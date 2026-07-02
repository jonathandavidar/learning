import io
import zipfile

from fastapi.testclient import TestClient

from src.app import app


client = TestClient(app)

SOURCE_TEXT = """
Threat Modeling for Web Applications

Threat modeling helps teams identify valuable assets, understand trust boundaries,
and anticipate likely attack paths before software is released. It improves team
alignment by making risk discussions concrete and repeatable.

A practical workflow starts by documenting the system, users, data flows, and
dependencies. Teams then review likely abuse cases, evaluate the impact of each
threat, and prioritize mitigations that reduce both likelihood and severity.

Threat models are most effective when they are revisited during design reviews,
implementation, and incident retrospectives. The output should guide secure design
decisions, testing priorities, and stakeholder communication.
""".strip()


def test_generate_course_returns_bloom_aligned_modules():
    response = client.post(
        "/api/course",
        json={
            "topic": "Threat Modeling",
            "source_text": SOURCE_TEXT,
            "bloom_level": 4,
        },
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["title"] == "Threat Modeling: Application Mini Course"
    assert 5 <= payload["estimated_duration_minutes"] <= 7
    assert payload["bloom_level"] == 4
    assert payload["bloom_label"] == "Analyze"
    assert len(payload["modules"]) >= 2

    for module in payload["modules"]:
        assert len(module["learning_objectives"]) == 2
        assert len(module["assessments"]) == len(module["learning_objectives"])
        assert all(
            assessment["objective"] in module["learning_objectives"]
            for assessment in module["assessments"]
        )

    assert payload["scorm"]["file_name"].endswith(".zip")
    assert "<manifest" in payload["scorm"]["manifest_preview"]


def test_scorm_download_contains_required_files():
    response = client.post(
        "/api/course/scorm",
        json={
            "source_text": SOURCE_TEXT,
            "bloom_level": 6,
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"

    archive = zipfile.ZipFile(io.BytesIO(response.content))
    assert sorted(archive.namelist()) == ["course.json", "imsmanifest.xml", "index.html"]

    manifest = archive.read("imsmanifest.xml").decode("utf-8")
    launch_page = archive.read("index.html").decode("utf-8")

    assert "<schemaversion>1.2</schemaversion>" in manifest
    assert "Application Mini Course" in launch_page


def test_invalid_bloom_level_is_rejected():
    response = client.post(
        "/api/course",
        json={
            "source_text": SOURCE_TEXT,
            "bloom_level": 2,
        },
    )

    assert response.status_code == 422
