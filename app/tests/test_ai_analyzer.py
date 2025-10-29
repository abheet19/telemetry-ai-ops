import pytest
from unittest.mock import patch
from app.ai.ai_analyzer import AIAnalyzer


@pytest.mark.parametrize(
    "data,expected_keyword",
    [
        ({"osnr": 35, "ber": 1e-9}, "healthy"),
        ({"osnr": 15, "ber": 1e-3}, "degraded"),
    ],
)
def test_ai_analyzer_mocked(data, expected_keyword):
    analyzer = AIAnalyzer()

    # Mock the OpenAI API call to avoid rate limits
    with patch.object(
        analyzer,
        "analyze_telemetry",
        return_value=f"[Mocked AI Analysis] {expected_keyword} link OK",
    ) as mock_ai:
        result = analyzer.analyze_telemetry(data)
        mock_ai.assert_called_once_with(data)
        assert expected_keyword in result.lower()
