from fastapi import FastAPI
from app.api import routes

def create_app() -> FastAPI:
    app= FastAPI(title="Telemetry AI OPS",version="1.0.0")
    app.include_router(routes.router)
    return app

app=create_app()