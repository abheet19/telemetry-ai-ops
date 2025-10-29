import asyncio
import random
from app.models import TelemetryRecord


async def fetch_telemetry(device_id: str) -> TelemetryRecord:
    await asyncio.sleep(random.uniform(0.5, 1.5))  # network delay

    return TelemetryRecord(
        device_id=device_id,
        wavelength=random.choice([1550.1, 1500.3, 1500.5]),
        osnr=random.uniform(18.0, 36.0),
        ber=random.choice([1e-9, 1e-6, 1e-3]),
        power_dbm=random.uniform(-22.0, 18.0),
    )


async def collect_all_devices(devices: list[str]):
    tasks = [fetch_telemetry(device) for device in devices]
    results = await asyncio.gather(*tasks)
    return results


def main():
    devices = [f"switch{i}" for i in range(1, 6)]
    results = asyncio.run(collect_all_devices(devices))
    for record in results:
        print(record.model_dump())


if __name__ == "__main__":
    main()
