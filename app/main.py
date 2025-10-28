from fastapi import FastAPI
from app.routes import telemetry
from app.services.pipeline import telemetry_pipeline, set_pipeline_state, is_pipeline_running
from contextlib import asynccontextmanager
import asyncio


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifecycle manager:
    - Starts the telemetry pipeline on startup.
    - Cancels it safely on shutdown.
    """
    # Start background task at startup
    print("[System] Starting telemetry pipeline task...")
    set_pipeline_state(True)
    pipeline_task = asyncio.create_task(telemetry_pipeline())
    app.state.pipeline_task = pipeline_task

    try:
        yield  # Application runs while yielded
    finally:
        # Graceful shutdown: stop pipeline, cancel async task
        print("[System] Shutting down telemetry pipeline...")
        set_pipeline_state(False)
        pipeline_task.cancel()
        try:
            await pipeline_task
        except asyncio.CancelledError:
            print("[System] Pipeline task cancelled cleanly.")
        except Exception as exc:
            print(f"[System] Pipeline shutdown error: {exc}")


def create_app() -> FastAPI:
    """
    Factory function to create and configure the FastAPI app.
    """
    app = FastAPI(
        title="Telemetry AI OPS",
        version="1.0.0",
        lifespan=lifespan
    )

    # Register routes
    app.include_router(telemetry.router)

    return app


# FastAPI app instance for Uvicorn
app = create_app()
