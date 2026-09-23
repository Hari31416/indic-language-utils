"""FastAPI application factory and static file serving for indic-language-utils."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from .. import __version__
from .routes import router

logger = logging.getLogger(__name__)


def _find_static_dir() -> Path | None:
    # 1. Check web/dist in repository root
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    web_dist = repo_root / "web" / "dist"
    if web_dist.is_dir() and (web_dist / "index.html").is_file():
        return web_dist

    # 2. Check bundled static dir inside package
    package_static = Path(__file__).resolve().parent / "static"
    if package_static.is_dir() and (package_static / "index.html").is_file():
        return package_static

    return None


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Indic Language Utils",
        version=__version__,
        description=(
            "REST API and UI for Indian language translation, transliteration, "
            "detection, and script identification"
        ),
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)

    static_dir = _find_static_dir()
    if static_dir is not None:
        logger.info("Serving static UI files from %s", static_dir)
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
    else:

        @app.get("/", response_class=HTMLResponse)
        async def root_fallback() -> str:
            return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Indic Language Utils</title>
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: #0f172a;
      color: #f8fafc;
      padding: 3rem;
      line-height: 1.6;
    }
    .card {
      max-width: 640px;
      margin: 0 auto;
      background: #1e293b;
      border-radius: 12px;
      padding: 2rem;
      border: 1px solid #334155;
    }
    h1 { margin-top: 0; font-size: 1.5rem; color: #38bdf8; }
    code { background: #0f172a; padding: 0.2rem 0.4rem; border-radius: 4px; font-size: 0.9em; }
    a { color: #38bdf8; text-decoration: none; }
    a:hover { text-decoration: underline; }
  </style>
</head>
<body>
  <div class="card">
    <h1>Indic Language Utils API</h1>
    <p>The backend service is running.</p>
    <p>To enable the web interface, build the frontend:</p>
    <pre><code>cd web &amp;&amp; pnpm install &amp;&amp; pnpm build</code></pre>
    <p>Explore API documentation at <a href="/docs">/docs</a> or <a href="/redoc">/redoc</a>.</p>
  </div>
</body>
</html>
"""

    return app


def run_server() -> None:
    """CLI entrypoint for running the server."""
    import uvicorn

    parser = argparse.ArgumentParser(description="Run indic-language-utils server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    args = parser.parse_args()

    uvicorn.run(
        "indic_language_utils.server.app:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
