# Mini Learning Engine API

A lightweight FastAPI application that turns provided source material into a
5-7 minute, application-oriented mini course.

## Features

- Analyze the full source text and break it into logical modules
- Generate Bloom's Taxonomy level 3-6 learning objectives for each module
- Create small assessments mapped to each learning objective
- Export the generated course as a SCORM 1.2 compatible zip package

## Getting Started

1. Install the dependencies:

   ```
   pip install -r ../requirements.txt
   ```

2. Run the application:

   ```
   python app.py
   ```

3. Open your browser and go to:

   - App UI: http://localhost:8000/static/index.html
   - API docs: http://localhost:8000/docs

## API Endpoints

| Method | Endpoint             | Description                                   |
| ------ | -------------------- | --------------------------------------------- |
| POST   | `/api/course`        | Generate the structured mini-course JSON      |
| POST   | `/api/course/scorm`  | Download the SCORM 1.2 package as a zip file  |
