"""
api/app.py
FastAPI application for Aviexa API.
Exposes Layers 1-3 through REST endpoints.
"""

import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from anomaly.detectors import AnomalyDetector
from bob import BobClient
from api.session_store import SessionStore
from api.routes import router, init_dependencies

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application.
    
    Returns:
        Configured FastAPI app
    """
    app = FastAPI(
        title="Aviexa API",
        description="AI-Powered ML Training Diagnostics API",
        version="1.0.0"
    )
    
    # Enable CORS for VS Code extension webviews
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # VS Code webviews
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Initialize dependencies
    session_store = SessionStore(ttl_hours=24)
    anomaly_detector = AnomalyDetector()
    bob_client = BobClient()
    
    # Initialize route dependencies
    init_dependencies(session_store, anomaly_detector, bob_client)
    
    # Include routes
    app.include_router(router)

    static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web")
    if os.path.isdir(static_dir):
        app.mount("/app", StaticFiles(directory=static_dir, html=True), name="app")
    
    # Root endpoint
    @app.get("/")
    async def root():
        return {
            "service": "Aviexa API",
            "version": "1.0.0",
            "status": "running",
            "endpoints": {
                "app": "/app",
                "health": "/health",
                "docs": "/docs",
                "sessions": "/sessions"
            }
        }
    
    logger.info("Aviexa API initialized")
    logger.info(f"Bob client mode: {'MOCK' if bob_client.use_mock else 'REAL'}")
    
    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("AVIEXA_API_PORT", "8765"))
    uvicorn.run(app, host="0.0.0.0", port=port)

# Made with Bob
