FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOME=/tmp \
    XDG_CACHE_HOME=/tmp/.cache \
    PYTHONPYCACHEPREFIX=/tmp/pycache

WORKDIR /app

# Install project (and dev tooling) into the image.
# At runtime we bind-mount the repo into /app, so the editable install points to the mounted code.
COPY pyproject.toml README.md /app/
COPY src /app/src

RUN python -m pip install --no-cache-dir -U pip setuptools wheel && \
    python -m pip install --no-cache-dir -e ".[dev]" && \
    python -m pip install --no-cache-dir notebook ipykernel
