import pytest
import asyncio
from unittest.mock import AsyncMock


@pytest.mark.asyncio
async def test_app_lifespan_starts_and_stops(monkeypatch):
    """Validate FastAPI lifespan:
    - starts pipeline task
    - starts/stops AI batcher cleanly
    """
    from app.main import create_app

    app = create_app()

    # Patch out background components
    mock_pipeline = AsyncMock()
    mock_batcher = AsyncMock()
    mock_batcher.start = AsyncMock()
    mock_batcher.stop = AsyncMock()

    monkeypatch.setattr("app.main.telemetry_pipeline", mock_pipeline)
    monkeypatch.setattr("app.main.AIBatcher", lambda analyzer=None: mock_batcher)

    # Run the lifespan manually
    async with app.router.lifespan_context(app):
        await asyncio.sleep(0.01)  # simulate runtime

    mock_batcher.start.assert_awaited()
    mock_batcher.stop.assert_awaited()
    assert hasattr(app.state, "ai_batcher")
