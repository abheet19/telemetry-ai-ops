from openai import OpenAI
from app.core.config import settings
import os
from app.services.pipeline import is_pipeline_running

client = OpenAI(api_key=settings.OPENAI_API_KEY)


class AIAnalyzer:
    """
    AI-based analysis of optical telemetry.
    Handles partial input and generates structured health analysis.
    """

    def analyze_telemetry(self, data: dict) -> str:
        """
        Generates a domain-specific optical telemetry analysis summary.
        """
        # Safe extraction with defaults
        device_id = data.get("device_id", "unknown_device")
        wavelength = data.get("wavelength", "N/A")
        osnr = data.get("osnr", "N/A")
        ber = data.get("ber", "N/A")
        power_dbm = data.get("power_dbm", "N/A")

        # Build a domain-specific prompt
        prompt = (
            f"Device {device_id} telemetry:\n"
            f"- Wavelength: {wavelength} nm\n"
            f"- OSNR: {osnr} dB\n"
            f"- BER: {ber}\n"
            f"- Power: {power_dbm} dBm\n\n"
            "As a Ciena optical systems engineer, analyze if this link is healthy or degraded. "
            "If degraded, suggest one practical action (e.g., power balancing, re-routing)."
        )

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )
            return response.choices[0].message.content
        except Exception as e:
            # return f"[Mock Analysis] OSNR={osnr}, BER={ber}, device={device_id}"
            return f"error: {e}"
        
    def run_ai_analysis(self,data:dict):
        """
        Background Task for AI Analysis
        """
        if not is_pipeline_running():
            print(f"[AI Analyzer] Skipped analysis — pipeline paused for device {data.get('device_id', 'unknown')}.")
            return
        device_id=data.get("device_id","unknown")
        try:
            insights=self.analyze_telemetry(data)
            print(f"[AI Insights] {device_id} -> {insights}")
        except Exception as e:
            print(f"[AI Error] {device_id}: {e}")