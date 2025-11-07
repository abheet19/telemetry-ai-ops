from typing import List, Dict, Any
from openai import AsyncOpenAI
from app.core.config import settings
import re
import json
import asyncio

# This file implements a hybrid analyzer:
#  - small fast heuristic rules handled locally (cheap)
#  - for harder cases, a batch AI call is simulated (replace with OpenAI call)
#  - run_ai_analysis_batch accepts a list and returns per-record responses


class AIAnalyzer:
    """Hybrid analyzer: heuristics + batched AI calls (async)."""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def run_ai_analysis(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze single record. For our day-5 flow we keep heuristics fast.
        Return a dict with status and optional message.
        """
        # Simple heuristic: high OSNR and very low BER => healthy
        osnr = record.get("osnr")
        ber = record.get("ber")
        if osnr is not None and ber is not None and osnr >= 30 and ber <= 1e-9:
            return {"status": "healthy", "reason": "heuristic_ok"}
        # fallback to alert (will be replaced by batch AI for ambiguous cases)
        return {"status": "needs_ai", "reason": "heuristic_uncertain"}

    async def run_ai_analysis_batch(
        self, batch: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Receive a batch of records and return analysis per record.
        Strategy:
          - apply heuristic to each item; gather the ones that require AI
          - if ai_needed list is empty -> return heuristics results
          - otherwise call external AI (here simulated) for only those items
        """
        try:
            # first pass: heuristics
            results: List[Dict[str, Any]] = []
            ai_needed = []
            ai_indices = []
            for i, rec in enumerate(batch):
                res = await self.run_ai_analysis(rec)
                if res.get("status") == "needs_ai":
                    ai_needed.append(rec)
                    ai_indices.append(i)
                    results.append(None)  # placeholder
                else:
                    results.append(res)

            if not ai_needed:
                return results

            # simulate async external AI call for ai_needed:
            ai_out = await self._call_external_ai_for_batch(ai_needed)
            print("AI Called")
            # merge responses back into results
            for idx, out in zip(ai_indices, ai_out):
                results[idx] = out
            return results
        except asyncio.CancelledError:
            print("[AIAnalyzer] Batch cancelled due to shutdown")
            raise

    async def _call_external_ai_for_batch(
        self, records: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Performs a real AI batch analysis using OpenAI Chat Completions API.
        Each record is summarized and analyzed by GPT-4o-mini.
        """
        # Build a combined batch prompt for multiple records
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert Ciena optical systems engineer. "
                    "Analyze optical telemetry data to determine if each link is healthy or degraded. "
                    "If degraded, suggest one practical action (e.g., power balancing, re-routing). "
                    "Return concise, structured output per record."
                ),
            },
            {
                "role": "user",
                "content": "\n".join(
                    [
                        f"Device {r.get('device_id','unknown')}: "
                        f"OSNR={r.get('osnr','N/A')} dB, "
                        f"BER={r.get('ber','N/A')}, "
                        f"Power={r.get('power_dbm','N/A')} dBm, "
                        f"Wavelength={r.get('wavelength','N/A')} nm."
                        for r in records
                    ]
                ),
            },
        ]

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0.3,
            )

            # Extract content
            raw_content = response.choices[0].message.content.strip()
            cleaned = re.sub(
                r"^```json|```$", "", raw_content, flags=re.MULTILINE
            ).strip()
            try:
                parsed = json.loads(cleaned)
            except json.JSONDecodeError:
                print("[AIAnalyzer] Non-JSON output, falling back to line mode.")
                parsed = None

            # Split lines heuristically per record (for now)
            results = []
            if isinstance(parsed, list):
                for rec, out in zip(records, parsed):
                    msg = out.get("Status") or out.get("message") or str(out)
                    print(f"[AI Insights] {rec.get('device_id')} → {msg}")
                    results.append(
                        {"device_id": rec.get("device_id"), "ai_output": out}
                    )
            else:
                # Fallback: split cleaned text line-by-line
                for rec, line in zip(records, cleaned.splitlines()):
                    print(f"[AI Insights] {rec.get('device_id')} → {line.strip()}")
                    results.append(
                        {"device_id": rec.get("device_id"), "message": line.strip()}
                    )

            return results

        except Exception as e:
            # Return structured fallback on API failure
            print("[AIAnalyzer] OpenAI call failed:", e)
            return [
                {
                    "status": "error",
                    "device_id": r.get("device_id"),
                    "message": f"AI analysis failed: {e}",
                }
                for r in records
            ]
