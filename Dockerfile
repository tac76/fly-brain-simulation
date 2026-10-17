# Fly Brain Simulation: editor server + viewer in one image.
#   docker build -t fly-brain-simulation .
#   docker run -p 127.0.0.1:8770:8770 -v flybrain-data:/app/data fly-brain-simulation
# Open http://127.0.0.1:8770/?editor . The FlyWire data (~135 MB, CC BY-NC 4.0) is downloaded
# into the volume on first start.

FROM node:22-slim AS viewer
WORKDIR /viewer
COPY viewer/package.json viewer/package-lock.json ./
RUN npm ci
COPY viewer/ ./
RUN npm run build

FROM python:3.12-slim
# MuJoCo needs these GL libraries even when nothing is rendered
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libegl1 libglfw3 libosmesa6 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY flybrain/ flybrain/
COPY server/ server/
COPY config/ config/
RUN uv sync --frozen --no-dev --no-group assets
COPY --from=viewer /viewer/dist viewer/dist
ENV MUJOCO_GL=egl PATH="/app/.venv/bin:$PATH"
VOLUME /app/data
EXPOSE 8770
CMD ["sh", "-c", "flybrain download-data && flybrain serve --host 0.0.0.0 --port 8770"]
