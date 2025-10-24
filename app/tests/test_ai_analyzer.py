from app.ai.ai_analyzer import AIAnalyzer

def test_ai_analyzer_healthy_signal():
    analyzer = AIAnalyzer()
    data = {"osnr": 35, "ber": 1e-9}
    result = analyzer.analyze_telemetry(data)
    assert "OSNR" in result or "healthy" in result.lower()

def test_ai_analyzer_alert_signal():
    analyzer = AIAnalyzer()
    data = {"osnr": 15, "ber": 1e-3}
    result = analyzer.analyze_telemetry(data)
    assert "OSNR" in result or "alert" in result.lower()