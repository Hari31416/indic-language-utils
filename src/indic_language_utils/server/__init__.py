"""FastAPI backend server for indic-language-utils."""

from .app import create_app, run_server

__all__ = ["create_app", "run_server"]
