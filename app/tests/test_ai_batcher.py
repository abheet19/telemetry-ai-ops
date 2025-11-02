import pytest
import asyncio
from unittest.mock import AsyncMock


@pytest.mark.asyncio
async def test_ai_batcher_enqueue_and_flush(monkeypatch):
    """Verify that enqueue collects records and flush triggers AI analysis."""
    from app.services.ai_batcher import AIBatcher

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
