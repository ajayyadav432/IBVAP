import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as api_router
from app.core.config import settings
from app.core.logging import sys_logger, camera_logger
from app.db.session import init_db, SessionLocal
from app.db.settings_store import load_runtime_settings
from app.models.schema import Camera
from app.services.events import connection_manager
from app.services.video.manager import camera_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context for startup and shutdown events."""
    sys_logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    sys_logger.info(f"Environment: {settings.IBVAP_ENV}, Debug: {settings.IBVAP_DEBUG}")
    
    # Set running event loop on connection_manager
    try:
        connection_manager.set_loop(asyncio.get_running_loop())
    except Exception:
        pass

    # Ensure evidence directories exist
    try:
        os.makedirs(os.path.join(settings.EVIDENCE_STORAGE_PATH, "events"), exist_ok=True)
    except Exception:
        pass

    # Initialize DB schema and load persisted runtime settings
    try:
        init_db()
        db = SessionLocal()
        load_runtime_settings(db)
        db.close()
        sys_logger.info("Database and settings initialized successfully.")
    except Exception as exc:
        sys_logger.error(f"Failed to initialize database and settings: {exc}")
        raise

    # Auto-start active cameras from DB (skip during automated test execution)
    if "PYTEST_CURRENT_TEST" not in os.environ and settings.IBVAP_ENV != "testing":
        try:
            db = SessionLocal()
            enabled_cameras = db.query(Camera).filter(Camera.enabled == True).all()
            for cam in enabled_cameras:
                camera_manager.register_camera(
                    camera_id=cam.id,
                    name=cam.name,
                    source_type=cam.source_type,
                    source_uri=cam.source_uri,
                    enabled=True,
                )
                camera_manager.reload_camera_zones(cam.id, cam.zones)
            camera_logger.info(f"Loaded {len(enabled_cameras)} active camera workers with zones on startup.")
            db.close()
        except Exception as exc:
            camera_logger.error(f"Error loading cameras on startup: {exc}")

    yield

    # Clean shutdown
    sys_logger.info(f"Shutting down {settings.APP_NAME}")
    camera_manager.stop_all()


def create_app() -> FastAPI:
    """FastAPI application factory."""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        docs_url="/docs" if settings.IBVAP_DEBUG else None,
        redoc_url="/redoc" if settings.IBVAP_DEBUG else None,
        lifespan=lifespan,
    )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount API routes
    app.include_router(api_router, prefix="/api")

    # Root WebSocket endpoint for direct ws://.../ws/events
    @app.websocket("/ws/events")
    async def root_websocket_events(websocket: WebSocket):
        await connection_manager.connect(websocket)
        try:
            while True:
                try:
                    await asyncio.wait_for(websocket.receive_text(), timeout=0.2)
                except asyncio.TimeoutError:
                    pass
        except WebSocketDisconnect:
            connection_manager.disconnect(websocket)
        except Exception:
            connection_manager.disconnect(websocket)

    # Mount static evidence directory if available
    if os.path.exists(settings.EVIDENCE_STORAGE_PATH):
        app.mount("/evidence", StaticFiles(directory=settings.EVIDENCE_STORAGE_PATH), name="evidence")

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.IBVAP_HOST,
        port=settings.IBVAP_PORT,
        reload=settings.IBVAP_DEBUG,
    )
