from app.models import TelemetryRecord
import pytest


def test_valid_telemetry_record():
    data = {
        "device_id": "optical_switch_1",
        "wavelength": 1550.0,
        "osnr": 32.5,
        "ber": 1e-9,
        "power_dbm": -3.2,
    }
    record = TelemetryRecord(**data)
    assert record.device_id == "optical_switch_1"
    assert record.osnr == 32.5
    assert record.ber < 1e-6


def test_invalid_telemetry_record():
    with pytest.raises(Exception):
        TelemetryRecord(device_id="x", wavelength="bad_data")
