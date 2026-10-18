# ---------------------------------------------------------------------------
# SAGE Backend Dockerfile (Render / Production)
# Python 3.11 Debian Bookworm Slim with Tectonic LaTeX Engine
# ---------------------------------------------------------------------------
FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TECTONIC_CACHE_DIR=/home/appuser/.cache/Tectonic \
    PORT=8000

# Install system dependencies for Tectonic font management and SSL/networking
RUN apt-get update && apt-get install -y --no-install-recommends \
    fontconfig \
    libfontconfig1 \
    libgraphite2-3 \
    libharfbuzz0b \
    libicu72 \
    libssl3 \
    zlib1g \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Pinned Tectonic release: statically linked musl build for x86_64 Linux
ARG TECTONIC_VERSION=0.15.0
ARG TECTONIC_URL=https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%40${TECTONIC_VERSION}/tectonic-${TECTONIC_VERSION}-x86_64-unknown-linux-musl.tar.gz

RUN curl -fsSL "${TECTONIC_URL}" -o /tmp/tectonic.tar.gz \
    && tar -xzf /tmp/tectonic.tar.gz -C /usr/local/bin \
    && rm -f /tmp/tectonic.tar.gz \
    && chmod +x /usr/local/bin/tectonic

# Create unprivileged application user and cache hierarchy
RUN useradd -m -u 1000 appuser \
    && mkdir -p /home/appuser/.cache/Tectonic /app \
    && chown -R appuser:appuser /home/appuser /app

WORKDIR /app

# Install Python dependencies first for optimal Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY --chown=appuser:appuser . /app

# Switch to non-root user
USER appuser

# Pre-bake the TeX bundle into TECTONIC_CACHE_DIR at image build time
# Runs a zero-LLM sample deck through the app's own Beamer renderer and compiler
# so required fonts and macro packages are cached and don't download on user requests.
RUN python -c "from app.models.schemas import SlideDeck, Slide, SlideDesignBrief; from app.core.slides import render_beamer, compile_beamer; deck = SlideDeck(title='Warmup', subtitle='Prebake', author='SAGE', short_title='Warmup', design_brief=SlideDesignBrief(audience='Engineers', narrative='Prebake', takeaways=['Ready']), slides=[Slide(layout='title', page_job='Warmup', title='Warmup'), Slide(layout='bullets', page_job='Warmup', title='Warmup', bullets=['Cached'])]); tex = render_beamer(deck); pdf, log = compile_beamer(tex); assert pdf is not None, f'Warmup compile failed: {log}'"

EXPOSE 8000

# Start Uvicorn bound to 0.0.0.0 and dynamic $PORT provided by Render
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --proxy-headers --forwarded-allow-ips='*'"]
