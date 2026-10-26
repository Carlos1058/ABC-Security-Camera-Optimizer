"""Entrypoint script for running the FastAPI application with Uvicorn."""

import uvicorn
from camera_optimizer.api.app import app

if __name__ == "__main__":
    uvicorn.run("camera_optimizer.main:app", host="127.0.0.1", port=8000, reload=True)
