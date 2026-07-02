document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("course-form");
  const downloadButton = document.getElementById("download-scorm");
  const output = document.getElementById("course-output");
  const messageDiv = document.getElementById("message");

  let lastPayload = null;

  function setMessage(text, type) {
    messageDiv.textContent = text;
    messageDiv.className = type;
  }

  function buildPayload() {
    return {
      topic: document.getElementById("topic").value.trim() || null,
      bloom_level: Number(document.getElementById("bloom-level").value),
      source_text: document.getElementById("source-text").value.trim(),
    };
  }

  function renderCourse(course) {
    const modules = course.modules
      .map(
        (module) => `
          <article class="course-card">
            <h3>${module.title}</h3>
            <p>${module.summary}</p>
            <p><strong>Source excerpt:</strong> ${module.source_excerpt}</p>
            <p><strong>Public knowledge bridge:</strong> ${module.public_knowledge_bridge}</p>
            <h4>Learning objectives</h4>
            <ul>
              ${module.learning_objectives.map((objective) => `<li>${objective}</li>`).join("")}
            </ul>
            <h4>Assessments</h4>
            <ol>
              ${module.assessments
                .map(
                  (assessment) => `
                    <li>
                      <strong>${assessment.type}:</strong> ${assessment.prompt}
                    </li>
                  `
                )
                .join("")}
            </ol>
          </article>
        `
      )
      .join("");

    output.innerHTML = `
      <article class="course-card">
        <h3>${course.title}</h3>
        <p><strong>Bloom level:</strong> ${course.bloom_level} - ${course.bloom_label}</p>
        <p><strong>Estimated duration:</strong> ${course.estimated_duration_minutes} minutes</p>
        <p><strong>SCORM package:</strong> ${course.scorm.file_name}</p>
      </article>
      ${modules}
    `;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const payload = buildPayload();
    try {
      const response = await fetch("/api/course", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });
      const result = await response.json();

      if (!response.ok) {
        throw new Error(result.detail || "Failed to generate course");
      }

      lastPayload = payload;
      downloadButton.disabled = false;
      renderCourse(result);
      setMessage("Mini course generated successfully.", "success");
    } catch (error) {
      downloadButton.disabled = true;
      setMessage(error.message || "Unable to generate the course.", "error");
    }
  });

  downloadButton.addEventListener("click", async () => {
    if (!lastPayload) {
      return;
    }

    try {
      const response = await fetch("/api/course/scorm", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(lastPayload),
      });

      if (!response.ok) {
        throw new Error("Unable to build SCORM package");
      }

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      const contentDisposition = response.headers.get("Content-Disposition") || "";
      const fileNameMatch = contentDisposition.match(/filename="(.+)"/);
      link.href = url;
      link.download = fileNameMatch ? fileNameMatch[1] : "mini-course.zip";
      link.click();
      URL.revokeObjectURL(url);
      setMessage("SCORM package downloaded.", "success");
    } catch (error) {
      setMessage(error.message || "Unable to download the SCORM package.", "error");
    }
  });
});
