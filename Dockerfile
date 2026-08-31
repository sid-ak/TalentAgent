# The review surface and agent loop, packaged for Cloud Run.
#
# Dependencies are installed from pyproject.toml so this file never restates them. The static
# surface and the launcher are copied separately because they are not part of the wheel, and
# TALENTAGENT_WEB_DIR points the server at them: the server's default web path is derived from
# the source-tree layout, which no longer holds once the package is installed.
FROM python:3.12-slim

WORKDIR /app

# Dependency layer. Copied first so edits to web/ or scripts/ do not invalidate the install.
COPY pyproject.toml README.md ./
COPY talentagent/ ./talentagent/
RUN pip install --no-cache-dir .

COPY web/ ./web/
COPY scripts/ ./scripts/
# The form-fill demo executes against these exact fixture forms, so they ship with the image.
COPY tests/fixtures/ats/ ./tests/fixtures/ats/

# Cloud Run injects PORT and routes to 0.0.0.0; the launcher reads both from the environment.
ENV HOST=0.0.0.0 \
    TALENTAGENT_WEB_DIR=/app/web \
    PYTHONUNBUFFERED=1

CMD ["python", "scripts/serve_demo.py"]
