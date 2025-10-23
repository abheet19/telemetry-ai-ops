from fastapi import FastAPI
from app.routes import telemetry

def create_app() -> FastAPI:
    app= FastAPI(title="Telemetry AI OPS",version="1.0.0")
    app.include_router(telemetry.router)
    return app

app=create_app()