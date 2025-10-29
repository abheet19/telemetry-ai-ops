from app.core.telemetry_queue import TelemetryQueue


def test_queue_enqueue_dequeue():
    q = TelemetryQueue()
    sample_data = {"device_id": "switch1", "osnr": 30.1}

    q.enqueue(sample_data)
    assert q.size() == 1
    assert not q.isEmpty()

    dequeued = q.dequeue()
    assert dequeued == sample_data
    assert q.size() == 0


def test_queue_empty_behavior():
    q = TelemetryQueue()
    assert q.dequeue() is None
    assert q.isEmpty()
