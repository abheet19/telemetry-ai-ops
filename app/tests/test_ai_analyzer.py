import pytest
from unittest.mock import AsyncMock, MagicMock
import json
from app.services.ai_analyzer import AIAnalyzer


@pytest.mark.asyncio
async def test_run_ai_analysis_heuristic_healthy():
    """Record with high OSNR and low BER should be marked healthy."""

    analyzer = AIAnalyzer()
    rec = {"osnr": 32.0, "ber": 1e-9}
    result = await analyzer.run_ai_analysis(rec)

    assert result["status"] == "healthy"
    assert result["reason"] == "heuristic_ok"


@pytest.mark.asyncio
async def test_run_ai_analysis_heuristic_needs_ai():
    """Record with poor OSNR/BER should need AI analysis."""

    analyzer = AIAnalyzer()
    rec = {"osnr": 10.0, "ber": 1e-4}
    result = await analyzer.run_ai_analysis(rec)

    assert result["status"] == "needs_ai"
    assert "heuristic_uncertain" in result["reason"]


@pytest.mark.asyncio
async def test_run_ai_analysis_batch_all_heuristic():
    """
    If all records are handled heuristically, analyzer should never call _call_external_ai_for_batch.
    """
    analyzer = AIAnalyzer()
    analyzer._call_external_ai_for_batch = AsyncMock()

    batch = [
        {"osnr": 35.0, "ber": 1e-9, "device_id": "sw1"},
        {"osnr": 33.0, "ber": 1e-10, "device_id": "amp1"},
    ]
    results = await analyzer.run_ai_analysis_batch(batch)

    assert analyzer._call_external_ai_for_batch.await_count == 0
    assert all(r["status"] == "healthy" for r in results)


@pytest.mark.asyncio
async def test_run_ai_analysis_batch_mixed(monkeypatch):
    """
    If some records need AI, _call_external_ai_for_batch should be invoked only for those.
    """
    analyzer = AIAnalyzer()

    async def fake_call(records):
        # Return dummy analysis per record
        return [{"status": "ai_ok", "device_id": r["device_id"]} for r in records]

    monkeypatch.setattr(analyzer, "_call_external_ai_for_batch", fake_call)

    batch = [
        {"osnr": 35.0, "ber": 1e-9, "device_id": "sw1"},
        {"osnr": 10.0, "ber": 1e-4, "device_id": "amp1"},
    ]
    results = await analyzer.run_ai_analysis_batch(batch)

    # 1 healthy (heuristic), 1 AI
    assert len(results) == 2
    assert results[0]["status"] == "healthy"
    assert results[1]["status"] == "ai_ok"


@pytest.mark.asyncio
async def test_call_external_ai_returns_valid_json(monkeypatch, capsys):
    """Simulate correct OpenAI JSON output."""

    fake_response = MagicMock()
    fake_response.choices = [
        MagicMock(
            message=MagicMock(
                content=json.dumps(
                    [
                        {"Device": "switch_1", "Status": "Healthy"},
                        {"Device": "amp_1", "Status": "Alert"},
                    ]
                )
            )
        )
    ]

    fake_client = AsyncMock()
    fake_client.chat.completions.create = AsyncMock(return_value=fake_response)
    monkeypatch.setattr(
        "app.services.ai_analyzer.AsyncOpenAI", lambda api_key: fake_client
    )

    analyzer = AIAnalyzer()
    recs = [{"device_id": "switch_1"}, {"device_id": "amp_1"}]
    results = await analyzer._call_external_ai_for_batch(recs)

    assert isinstance(results, list)
    assert len(results) == 2
    assert all("device_id" in r for r in results)
    captured = capsys.readouterr().out
    assert "AI Insights" in captured


@pytest.mark.asyncio
async def test_call_external_ai_handles_non_json(monkeypatch, capsys):
    """Handle non-JSON outputs gracefully."""
    fake_response = MagicMock()
    fake_response.choices = [
        MagicMock(
            message=MagicMock(
                content="Device switch_1: Looks fine\nDevice amp_1: High BER"
            )
        )
    ]

    fake_client = AsyncMock()
    fake_client.chat.completions.create = AsyncMock(return_value=fake_response)
    monkeypatch.setattr(
        "app.services.ai_analyzer.AsyncOpenAI", lambda api_key: fake_client
    )

    analyzer = AIAnalyzer()
    recs = [{"device_id": "switch_1"}, {"device_id": "amp_1"}]
    results = await analyzer._call_external_ai_for_batch(recs)

    assert len(results) == 2
    assert all("message" in r for r in results)
    captured = capsys.readouterr().out
    assert "[AI Insights]" in captured


@pytest.mark.asyncio
async def test_call_external_ai_handles_exception(monkeypatch, capsys):
    """If OpenAI API call fails, analyzer should return structured error messages."""

    fake_client = AsyncMock()
    fake_client.chat.completions.create = AsyncMock(
        side_effect=RuntimeError("Network issue")
    )
    monkeypatch.setattr(
        "app.services.ai_analyzer.AsyncOpenAI", lambda api_key: fake_client
    )

    analyzer = AIAnalyzer()
    recs = [{"device_id": "switch_1"}]
    results = await analyzer._call_external_ai_for_batch(recs)

    assert len(results) == 1
    assert results[0]["status"] == "error"
    assert "AI analysis failed" in results[0]["message"]
    captured = capsys.readouterr().out
    assert "OpenAI call failed" in captured
