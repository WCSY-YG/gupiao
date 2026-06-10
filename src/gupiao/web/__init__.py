"""Web dashboard and local app generation."""

from gupiao.web.dashboard import build_dashboard_html, write_dashboard_html
from gupiao.web.server import build_app_html, run_web_action, serve_app

__all__ = [
    "build_app_html",
    "build_dashboard_html",
    "run_web_action",
    "serve_app",
    "write_dashboard_html",
]
