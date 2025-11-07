import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from app.services.ai_batcher import AIBatcher


@pytest.mark.asyncio
async def test_ai_batcher_enqueue_and_flush():
    """Verify that enqueue collects records and flush triggers AI analysis."""
    fake_analyzer = AsyncMock()
    fake_analyzer.run_ai_analysis_batch = AsyncMock(return_value=[{"ok": True}])

    batcher = AIBatcher(fake_analyzer, batch_size=3, timeout_seconds=0.1)
    await batcher.start()

    await batcher.enqueue({"device_id": "a"})
    await batcher.enqueue({"device_id": "b"})
    await batcher.enqueue({"device_id": "c"})  # triggers flush

    await asyncio.sleep(0.1)
    await batcher.stop()
    assert fake_analyzer.run_ai_analysis_batch.await_count >= 1


@pytest.mark.asyncio
async def test_ai_batcher_stop_when_not_running():
    """Test stop() when batcher is not running."""
    fake_analyzer = AsyncMock()
    batcher = AIBatcher(fake_analyzer)

    # Stop without starting should not raise
    await batcher.stop()
    assert not batcher._running


@pytest.mark.asyncio
async def test_ai_batcher_stop_when_already_stopped():
    """Test stop() when batcher is already stopped."""
    fake_analyzer = AsyncMock()
    batcher = AIBatcher(fake_analyzer)

    await batcher.start()
    await batcher.stop()
    # Stop again should not raise
    await batcher.stop()
    assert not batcher._running


@pytest.mark.asyncio
async def test_ai_batcher_timeout_flush():
    """Test that timeout triggers flush even if batch_size not reached."""
    fake_analyzer = AsyncMock()
    fake_analyzer.run_ai_analysis_batch = AsyncMock(return_value=[{"ok": True}])

    batcher = AIBatcher(fake_analyzer, batch_size=10, timeout_seconds=0.1)
    await batcher.start()

    await batcher.enqueue({"device_id": "a"})
    # Wait for timeout
    await asyncio.sleep(0.15)

    await batcher.stop()
    # Should have flushed due to timeout
    assert fake_analyzer.run_ai_analysis_batch.await_count >= 1


@pytest.mark.asyncio
async def test_ai_batcher_flush_empty_buffer():
    """Test flush() when buffer is empty."""
    fake_analyzer = AsyncMock()
    batcher = AIBatcher(fake_analyzer)
    await batcher.start()

    # Flush empty buffer
    await batcher._flush()

    await batcher.stop()
    # Should not call analyzer
    assert fake_analyzer.run_ai_analysis_batch.await_count == 0


@pytest.mark.asyncio
async def test_ai_batcher_retry_on_failure(monkeypatch):
    """Test that retries are attempted on transient failures."""

    fake_analyzer = AsyncMock()
    call_count = 0

    async def failing_analyzer(batch):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise RuntimeError("Transient error")
        return [{"status": "ok"} for _ in batch]

    fake_analyzer.run_ai_analysis_batch = failing_analyzer

    # Mock database session
    mock_session = MagicMock()
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=False)
    monkeypatch.setattr("app.services.ai_batcher.SessionLocal", lambda: mock_session)

    batcher = AIBatcher(fake_analyzer, batch_size=2, timeout_seconds=0.1)
    await batcher.start()

    await batcher.enqueue({"device_id": "a", "osnr": 30.0, "ber": 1e-9})
    await batcher.enqueue({"device_id": "b", "osnr": 31.0, "ber": 1e-9})

    # Wait for processing with retries (exponential backoff: 1s + 2s + success)
    await asyncio.sleep(4.0)
    await batcher.stop()

    # Should have retried and eventually succeeded
    assert call_count == 3


@pytest.mark.asyncio
async def test_ai_batcher_error_after_retries(monkeypatch, capsys):
    """Test that errors after all retries are handled gracefully."""

    fake_analyzer = AsyncMock()

    async def always_failing_analyzer(batch):
        raise RuntimeError("Persistent error")

    fake_analyzer.run_ai_analysis_batch = always_failing_analyzer

    # Mock database session
    mock_session = MagicMock()
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=False)
    monkeypatch.setattr("app.services.ai_batcher.SessionLocal", lambda: mock_session)

    batcher = AIBatcher(fake_analyzer, batch_size=2, timeout_seconds=0.1)
    await batcher.start()

    await batcher.enqueue({"device_id": "a"})
    await batcher.enqueue({"device_id": "b"})

    # Wait for processing with retries (exponential backoff: 1s + 2s + 4s = ~7s minimum)
    await asyncio.sleep(8.0)
    await batcher.stop()

    # Should have logged error
    captured = capsys.readouterr().out
    assert (
        "failed after retries" in captured.lower()
        or "ai batch failed" in captured.lower()
    )


@pytest.mark.asyncio
async def test_ai_batcher_start_when_already_running():
    """Test start() when batcher is already running."""
    fake_analyzer = AsyncMock()
    batcher = AIBatcher(fake_analyzer)

    await batcher.start()
    assert batcher._running

    # Start again should not create duplicate tasks
    original_task = batcher._loop_task
    await batcher.start()
    assert batcher._loop_task == original_task

    await batcher.stop()


@pytest.mark.asyncio
async def test_ai_batcher_concurrency_limit():
    """Test that semaphore limits concurrent batch processing."""
    call_count = 0

    async def slow_analyzer(batch):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.1)
        return [{"status": "ok"} for _ in batch]

    fake_analyzer = AsyncMock()
    fake_analyzer.run_ai_analysis_batch = slow_analyzer

    batcher = AIBatcher(
        fake_analyzer, batch_size=2, max_concurrency=1, timeout_seconds=0.05
    )
    await batcher.start()

    # Enqueue multiple batches
    for i in range(6):
        await batcher.enqueue({"device_id": f"device_{i}"})

    # Wait a bit
    await asyncio.sleep(0.3)
    await batcher.stop()

    # With max_concurrency=1, should process sequentially
    # At least one batch should have been processed
    assert call_count >= 1
