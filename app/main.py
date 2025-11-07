from fastapi import FastAPI
from app.routes import telemetry, metrics
from app.core.database import Base, engine
from app.services.pipeline import telemetry_pipeline, set_pipeline_state
from app.services.ai_analyzer import AIAnalyzer
from app.services.ai_batcher import AIBatcher
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
    print("[System] Starting telemetry pipeline and AI batcher...")
    set_pipeline_state(True)

    analyzer = AIAnalyzer()
    ai_batcher = AIBatcher(analyzer)
    await ai_batcher.start()
    app.state.ai_batcher = ai_batcher

    # Create database tables at startup
    Base.metadata.create_all(bind=engine)

    pipeline_task = asyncio.create_task(telemetry_pipeline())
    app.state.pipeline_task = pipeline_task

    try:
        yield  # Application runs while yielded
    finally:
        # Graceful shutdown: stop pipeline, cancel async task
        print("[System] Shutting down telemetry pipeline and AI batcher...")
        set_pipeline_state(False)
        pipeline_task.cancel()
        try:
            await pipeline_task
        except asyncio.CancelledError:
            print("[System] Pipeline task cancelled cleanly.")
        except Exception as exc:
            print(f"[System] Pipeline shutdown error: {exc}")

        await ai_batcher.stop()


def create_app() -> FastAPI:
    """
    Factory function to create and configure the FastAPI app.
    """
    app = FastAPI(title="Telemetry AI OPS", version="1.0.0", lifespan=lifespan)
    app.include_router(telemetry.router)
    app.include_router(metrics.router)
    return app


app = create_app()
