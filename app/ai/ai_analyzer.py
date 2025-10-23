import os
from openai import OpenAI
from app.core.config import settings

client = OpenAI(api_key=settings.OPENAI_API_KEY)

class AIAnalyzer:
    def analyze_telemetry(self,data: dict) -> str:
        """
        AI-based analysis of optical telemetry.
        Generates concise health summaries for Ciena-like telemetry.
        """
        prompt = (
            f"Device {data['device_id']} telemetry:\n"
            f"- Wavelength: {data['wavelength']} nm\n"
            f"- OSNR: {data['osnr']} dB\n"
            f"- BER: {data['ber']}\n"
            f"- Power: {data.get('power_dbm', 'N/A')} dBm\n\n"
            "As a Ciena optical systems engineer, analyze if this link is healthy or degraded. "
            "If degraded, suggest one practical action (e.g., power balancing, re-routing)."
        )

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )

        return response.choices[0].message.content