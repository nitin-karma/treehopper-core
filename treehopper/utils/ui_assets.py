import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_swagger_ui_html

# __file__ is treehopper/utils/ui_assets.py
STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")
STATIC_DIR = os.path.abspath(STATIC_DIR)  # normalize to absolute path

# Define the browser-accessible URL path for the favicon
FAVICON_URL_PATH = "/static/treehopper_favicon.png"


def inject_branding(app: FastAPI, title: str):
    app.title = f"{title} | Treehopper"
    app.description = (
        "⚡️ Powered by Treehopper — Automate LLM workflows with agents & chains"
    )
    app.redoc_url = None
    app.openapi_url = "/openapi.json"

    # disable default docs
    app.docs_url = None

    # mount static dir if it exists. All files in STATIC_DIR are now accessible via /static/
    if os.path.isdir(STATIC_DIR):
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/docs", include_in_schema=False)
    async def custom_swagger_ui_html():
        # CORRECT: Use the browser-accessible URL path, not the server's file path.
        return get_swagger_ui_html(
            openapi_url=app.openapi_url,
            title=app.title,
            swagger_favicon_url=FAVICON_URL_PATH,
        )
