from fastapi import FastAPI
from app.routes import telemetry
from app.services.pipeline import telemetry_pipeline
from contextlib import asynccontextmanager
import asyncio

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start background task at startup
    task = asyncio.create_task(telemetry_pipeline())
    app.state.telemetry_task = task

    try:
        yield  # application runs while we are yielded
    finally:
        # On shutdown: cancel the background task and wait for it to finish
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            pass

def create_app() -> FastAPI:
    app= FastAPI(title="Telemetry AI OPS",version="1.0.0",lifespan=lifespan)
    app.include_router(telemetry.router)

    return app

app=create_app()