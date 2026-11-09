"""
PL Capital Financial Intelligence Agent - Primary ASGI Application Entrypoint.
Exposes the core FastAPI application for Vercel Serverless Functions, Uvicorn, and ASGI containers.
"""
import sys

# If invoked via streamlit run app.py, delegate execution to streamlit_app.py
if any("streamlit" in arg.lower() for arg in sys.argv):
    import runpy
    from pathlib import Path
    st_path = Path(__file__).resolve().parent / "streamlit_app.py"
    if st_path.exists():
        runpy.run_path(str(st_path), run_name="__main__")

from api import app

__all__ = ["app"]
