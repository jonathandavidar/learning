"""
Mini learning engine API.

A lightweight FastAPI application that transforms source text into a short,
application-oriented mini course aligned to Bloom's Taxonomy levels 3-6 and
exports a SCORM 1.2 compatible package.
"""

from __future__ import annotations

import html
import io
import json
import os
import re
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

app = FastAPI(
    title="Mini Learning Engine",
    description=(
        "Transforms provided text into a Bloom-aligned, SCORM-compatible "
        "micro-course."
    ),
)

app.mount(
    "/static",
    StaticFiles(directory=os.path.join(Path(__file__).parent, "static")),
    name="static",
)

STOP_WORDS = {
    "about",
    "after",
    "again",
    "also",
    "because",
    "between",
    "could",
    "every",
    "first",
    "from",
    "into",
    "just",
    "more",
    "most",
    "other",
    "over",
    "such",
    "than",
    "that",
    "their",
    "there",
    "these",
    "they",
    "this",
    "those",
    "through",
    "using",
    "very",
    "what",
    "when",
    "where",
    "which",
    "while",
    "with",
    "would",
    "your",
}

BLOOM_LEVELS = {
    3: {
        "label": "Apply",
        "verbs": ("apply", "use"),
        "assessment": "scenario response",
    },
    4: {
        "label": "Analyze",
        "verbs": ("analyze", "differentiate"),
        "assessment": "analysis prompt",
    },
    5: {
        "label": "Evaluate",
        "verbs": ("evaluate", "justify"),
        "assessment": "judgment prompt",
    },
    6: {
        "label": "Create",
        "verbs": ("design", "produce"),
        "assessment": "creation challenge",
    },
}


class CourseRequest(BaseModel):
    topic: str | None = Field(
        default=None, description="Optional topic name used in the course title."
    )
    source_text: str = Field(
        min_length=80, description="The source material used to generate the course."
    )
    bloom_level: int = Field(
        default=3, ge=3, le=6, description="Bloom's Taxonomy level (3-6)."
    )


class ScormPreview(BaseModel):
    file_name: str
    manifest_preview: str
    launch_page: str


class CourseResponse(BaseModel):
    title: str
    topic: str
    bloom_level: int
    bloom_label: str
    estimated_duration_minutes: int
    source_word_count: int
    modules: list[dict[str, Any]]
    scorm: ScormPreview


@app.get("/")
def root() -> RedirectResponse:
    return RedirectResponse(url="/static/index.html")


@app.post("/api/course", response_model=CourseResponse)
def generate_course(request: CourseRequest) -> CourseResponse:
    course = build_course(request)
    manifest = build_scorm_manifest(course["identifier"], course["title"])
    return CourseResponse(
        **course,
        scorm=ScormPreview(
            file_name=f"{course['identifier']}.zip",
            manifest_preview=manifest,
            launch_page="index.html",
        ),
    )


@app.post("/api/course/scorm")
def download_scorm_package(request: CourseRequest) -> StreamingResponse:
    course = build_course(request)
    package = build_scorm_package(course)
    return StreamingResponse(
        io.BytesIO(package),
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{course["identifier"]}.zip"'
            )
        },
    )


def build_course(request: CourseRequest) -> dict[str, Any]:
    normalized_text = normalize_text(request.source_text)
    topic = normalize_topic(request.topic) or infer_topic(normalized_text)
    sections = split_into_sections(normalized_text)
    chunks = group_sections(sections)
    modules = [
        build_module(index=index, topic=topic, bloom_level=request.bloom_level, chunk=chunk)
        for index, chunk in enumerate(chunks, start=1)
    ]

    return {
        "identifier": slugify(topic) or "mini-learning-course",
        "title": f"{topic}: Application Mini Course",
        "topic": topic,
        "bloom_level": request.bloom_level,
        "bloom_label": BLOOM_LEVELS[request.bloom_level]["label"],
        "estimated_duration_minutes": min(7, max(5, len(modules) + 3)),
        "source_word_count": len(normalized_text.split()),
        "modules": modules,
    }


def normalize_text(source_text: str) -> str:
    lines = [line.strip() for line in source_text.splitlines()]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def normalize_topic(topic: str | None) -> str | None:
    if not topic:
        return None
    cleaned = re.sub(r"\s+", " ", topic).strip()
    return cleaned or None


def infer_topic(text: str) -> str:
    title_candidate = text.splitlines()[0].strip()
    if 3 <= len(title_candidate) <= 80 and not title_candidate.endswith((".", "!", "?")):
        return title_candidate

    keywords = extract_keywords(text, limit=3)
    if keywords:
        return " ".join(word.title() for word in keywords)
    return "Source Topic"


def split_into_sections(text: str) -> list[dict[str, str]]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    if len(paragraphs) > 1:
        return [build_section_from_paragraph(paragraph) for paragraph in paragraphs]

    sentences = split_sentences(text)
    if len(sentences) <= 4:
        return [{"heading": "Core Ideas", "content": text}]

    section_size = max(2, len(sentences) // 3)
    sections = []
    for start in range(0, len(sentences), section_size):
        chunk = " ".join(sentences[start : start + section_size]).strip()
        if chunk:
            sections.append(build_section_from_paragraph(chunk))
    return sections


def build_section_from_paragraph(paragraph: str) -> dict[str, str]:
    lines = [line.strip() for line in paragraph.splitlines() if line.strip()]
    if len(lines) > 1 and len(lines[0].split()) <= 8 and not lines[0].endswith((".", "!", "?")):
        heading = lines[0]
        content = " ".join(lines[1:])
    else:
        heading = derive_heading(paragraph)
        content = " ".join(lines)
    return {"heading": heading, "content": content}


def group_sections(sections: list[dict[str, str]]) -> list[dict[str, Any]]:
    max_modules = 4
    if len(sections) <= max_modules:
        return [
            {"title": section["heading"], "content": section["content"]}
            for section in sections
        ]

    target_size = max(1, (len(sections) + max_modules - 1) // max_modules)
    grouped = []
    for start in range(0, len(sections), target_size):
        slice_sections = sections[start : start + target_size]
        grouped.append(
            {
                "title": slice_sections[0]["heading"],
                "content": " ".join(section["content"] for section in slice_sections),
            }
        )
    return grouped[:max_modules]


def build_module(
    *, index: int, topic: str, bloom_level: int, chunk: dict[str, Any]
) -> dict[str, Any]:
    title = chunk["title"] or f"Module {index}"
    content = chunk["content"]
    keywords = extract_keywords(content, limit=3)
    focus = ", ".join(keywords) if keywords else "the core ideas"
    summary = summarize_text(content)
    objectives = build_learning_objectives(
        module_title=title,
        module_focus=focus,
        topic=topic,
        bloom_level=bloom_level,
    )
    return {
        "module_id": f"module-{index}",
        "title": title,
        "summary": summary,
        "source_excerpt": trim_text(content, 260),
        "public_knowledge_bridge": (
            f"In public practice, {topic.lower()} is strongest when people connect "
            f"{focus} to stakeholders, measurable outcomes, risks, and feedback loops."
        ),
        "learning_objectives": objectives,
        "assessments": build_assessments(
            module_title=title,
            module_focus=focus,
            objectives=objectives,
            bloom_level=bloom_level,
        ),
    }


def build_learning_objectives(
    *, module_title: str, module_focus: str, topic: str, bloom_level: int
) -> list[str]:
    primary_verb, secondary_verb = BLOOM_LEVELS[bloom_level]["verbs"]
    return [
        (
            f"{primary_verb.title()} the ideas from {module_title} to a realistic "
            f"{topic.lower()} situation involving {module_focus}."
        ),
        (
            f"{secondary_verb.title()} decisions, evidence, and trade-offs in "
            f"{module_title} to improve outcomes."
        ),
    ]


def build_assessments(
    *,
    module_title: str,
    module_focus: str,
    objectives: list[str],
    bloom_level: int,
) -> list[dict[str, Any]]:
    assessment_type = BLOOM_LEVELS[bloom_level]["assessment"]
    assessments = []
    for index, objective in enumerate(objectives, start=1):
        assessments.append(
            {
                "assessment_id": f"{slugify(module_title)}-assessment-{index}",
                "type": assessment_type,
                "objective": objective,
                "prompt": (
                    f"Use {module_title} to respond to a short workplace or classroom "
                    f"scenario involving {module_focus}. What would you do and why?"
                ),
                "success_criteria": [
                    "References the module's main idea",
                    "Applies evidence from the source material",
                    "Explains the choice or recommendation clearly",
                ],
            }
        )
    return assessments


def summarize_text(text: str) -> str:
    sentences = split_sentences(text)
    if not sentences:
        return trim_text(text, 180)
    return " ".join(sentences[:2]).strip()


def split_sentences(text: str) -> list[str]:
    return [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", text) if sentence.strip()]


def derive_heading(text: str) -> str:
    words = extract_keywords(text, limit=3)
    if words:
        return " / ".join(word.title() for word in words)
    return "Learning Segment"


def extract_keywords(text: str, limit: int = 3) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z\-']+", text.lower())
    filtered = [
        word
        for word in words
        if len(word) > 3 and word not in STOP_WORDS and not word.isdigit()
    ]
    counts = Counter(filtered)
    return [word for word, _ in counts.most_common(limit)]


def trim_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3].rstrip()}..."


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "course"


def build_scorm_package(course: dict[str, Any]) -> bytes:
    manifest = build_scorm_manifest(course["identifier"], course["title"])
    launch_page = build_scorm_launch_page(course)
    course_json = json.dumps(course, indent=2)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("imsmanifest.xml", manifest)
        archive.writestr("index.html", launch_page)
        archive.writestr("course.json", course_json)
    return buffer.getvalue()


def build_scorm_manifest(identifier: str, title: str) -> str:
    safe_identifier = html.escape(identifier, quote=True)
    safe_title = html.escape(title)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<manifest identifier="{safe_identifier}" version="1.2"
  xmlns="http://www.imsproject.org/xsd/imscp_rootv1p1p2"
  xmlns:adlcp="http://www.adlnet.org/xsd/adlcp_rootv1p2"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  xsi:schemaLocation="http://www.imsproject.org/xsd/imscp_rootv1p1p2 imscp_rootv1p1p2.xsd
  http://www.adlnet.org/xsd/adlcp_rootv1p2 adlcp_rootv1p2.xsd">
  <metadata>
    <schema>ADL SCORM</schema>
    <schemaversion>1.2</schemaversion>
  </metadata>
  <organizations default="ORG-1">
    <organization identifier="ORG-1">
      <title>{safe_title}</title>
      <item identifier="ITEM-1" identifierref="RES-1">
        <title>{safe_title}</title>
      </item>
    </organization>
  </organizations>
  <resources>
    <resource identifier="RES-1" type="webcontent" adlcp:scormtype="sco" href="index.html">
      <file href="index.html" />
      <file href="course.json" />
    </resource>
  </resources>
</manifest>
"""


def build_scorm_launch_page(course: dict[str, Any]) -> str:
    module_markup = []
    for module in course["modules"]:
        objectives = "".join(
            f"<li>{html.escape(objective)}</li>"
            for objective in module["learning_objectives"]
        )
        assessments = "".join(
            (
                "<li>"
                f"<strong>{html.escape(assessment['type'].title())}:</strong> "
                f"{html.escape(assessment['prompt'])}"
                "</li>"
            )
            for assessment in module["assessments"]
        )
        module_markup.append(
            f"""
            <section class="module">
              <h2>{html.escape(module['title'])}</h2>
              <p>{html.escape(module['summary'])}</p>
              <p><strong>Public knowledge bridge:</strong> {html.escape(module['public_knowledge_bridge'])}</p>
              <h3>Learning objectives</h3>
              <ul>{objectives}</ul>
              <h3>Quick assessments</h3>
              <ol>{assessments}</ol>
            </section>
            """
        )

    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{html.escape(course['title'])}</title>
    <style>
      body {{
        font-family: Arial, sans-serif;
        line-height: 1.6;
        margin: 0 auto;
        max-width: 960px;
        padding: 24px;
        color: #1f2933;
        background: #f5f7fa;
      }}
      header, .module {{
        border: 1px solid #d9e2ec;
        border-radius: 8px;
        padding: 20px;
        margin-bottom: 20px;
        background: #fff;
      }}
      h1, h2, h3 {{
        color: #102a43;
      }}
    </style>
  </head>
  <body>
    <header>
      <h1>{html.escape(course['title'])}</h1>
      <p><strong>Topic:</strong> {html.escape(course['topic'])}</p>
      <p><strong>Bloom level:</strong> {course['bloom_level']} - {html.escape(course['bloom_label'])}</p>
      <p><strong>Estimated duration:</strong> {course['estimated_duration_minutes']} minutes</p>
    </header>
    {''.join(module_markup)}
  </body>
</html>
"""


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
