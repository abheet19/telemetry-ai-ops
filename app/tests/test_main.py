import pytest
import asyncio
from unittest.mock import AsyncMock

# Note: patch is imported for potential future use but not currently used


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


@pytest.mark.asyncio
async def test_app_lifespan_pipeline_cancelled_error(monkeypatch):
    """Test lifespan handles CancelledError during pipeline shutdown."""
    from app.main import create_app

    app = create_app()

    mock_batcher = AsyncMock()
    mock_batcher.start = AsyncMock()
    mock_batcher.stop = AsyncMock()

    # Create a task that will be cancelled
    async def mock_pipeline():
        # This will run until cancelled
        try:
            while True:
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            raise

    # Store the original create_task
    original_create_task = asyncio.create_task

    def create_cancelled_task(coro):
        # Create the task from the coroutine (this schedules it, avoiding the warning)
        task = original_create_task(coro)
        # Cancel it immediately
        task.cancel()
        return task

    monkeypatch.setattr("app.main.telemetry_pipeline", mock_pipeline)
    monkeypatch.setattr("app.main.AIBatcher", lambda analyzer=None: mock_batcher)
    monkeypatch.setattr("app.main.asyncio.create_task", create_cancelled_task)

    # Run the lifespan manually
    async with app.router.lifespan_context(app):
        await asyncio.sleep(0.01)

    # Should handle CancelledError gracefully
    mock_batcher.stop.assert_awaited()


@pytest.mark.asyncio
async def test_app_lifespan_pipeline_shutdown_exception(monkeypatch, capsys):
    """Test lifespan handles general Exception during pipeline shutdown."""
    from app.main import create_app

    app = create_app()

    mock_batcher = AsyncMock()
    mock_batcher.start = AsyncMock()
    mock_batcher.stop = AsyncMock()

    # Create a mock task that raises Exception (not CancelledError) when awaited
    async def exception_coro():
        raise RuntimeError("Pipeline shutdown error")

    exception_iter = exception_coro().__await__()

    class ExceptionTask:
        def cancel(self):
            pass

        def __await__(self):
            return exception_iter

    exception_task = ExceptionTask()

    # Create a proper async function for the pipeline that will be used to create a task
    async def mock_pipeline():
        # This will run until cancelled or exception
        try:
            await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            raise

    # Store the original create_task
    original_create_task = asyncio.create_task

    def create_exception_task_wrapper(coro):
        # Create the task from the coroutine (this schedules it, avoiding the warning)
        original_create_task(coro)
        # Return our exception task instead - this function should be covered
        return exception_task

    monkeypatch.setattr("app.main.telemetry_pipeline", mock_pipeline)
    monkeypatch.setattr("app.main.AIBatcher", lambda analyzer=None: mock_batcher)
    monkeypatch.setattr("app.main.asyncio.create_task", create_exception_task_wrapper)

    # Run the lifespan manually
    async with app.router.lifespan_context(app):
        await asyncio.sleep(0.01)

    # Should handle Exception gracefully and print error
    mock_batcher.stop.assert_awaited()
    captured = capsys.readouterr().out
    # The exception handling should have printed an error message
    assert "Pipeline shutdown error" in captured or "shutdown" in captured.lower()


def test_create_app():
    """Test create_app factory function."""
    from app.main import create_app

    app = create_app()
    assert app.title == "Telemetry AI OPS"
    assert app.version == "1.0.0"
    # Check that routers are included
    assert len(app.routes) > 0
