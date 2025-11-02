import asyncio
import time
from typing import List, Dict, Any, Optional
from tenacity import (
    AsyncRetrying,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from prometheus_client import Summary, Counter, Gauge

AI_LATENCY = Summary(
    "ai_inference_latency_seconds", "Latency for AI inference(seconds)"
)
AI_CALLS = Counter("ai_calls_total", "Total AI calls attempted")
AI_ERRORS = Counter("ai_errors_total", "Total AI errors")
QUEQUE_SIZE = Gauge(
    "telemetry_batch_queue_size", "Current size of batched telemetry buffer"
)


class AIBatcher:
    """
    AIBatcher buffers telemetry records and dispatches them to the analyzer in batches.
    -flush when batch reaches batch_size
    -flush when timeout_seconds elapses since last flush event
    -concurrency limited via semaphore
    -retries on transient errors using tenacity(exponential backoff)
    -non blocking API :enqueue() returns quickly
    """

    def __init__(
        self,
        analyzer,
        batch_size: int = 16,
        timeout_seconds: float = 12.0,
        max_concurrency: int = 2,
    ):
        self.analyzer = analyzer
        self.batch_size = batch_size
        self.timeout_seconds = timeout_seconds
        self._buffer: List[Dict[str, Any]] = []
        self._buffer_lock = asyncio.Lock()
        self._flush_event = asyncio.Event()
        self._running = False
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._loop_task: Optional(asyncio.Task) = None

    async def start(self):
        # Start background loop
        if self._running:
            return
        self._running = True
        # create background task that manages flush by timeout or slice
        self._loop_task = asyncio.create_task(self._batch_loop())

    async def stop(self):
        # Stop the batcher and flush remaining records
        if not self._running:
            return

        self._running = False
        # wake up loop so it can exit quickly
        self._flush_event.set()
        if self._loop_task:
            await self._loop_task  # wait for loop to exit cleanly

        await self._flush()

    async def enqueue(self, record: Dict[str, Any]):
        # add record to buffer, trigger immediate flush if size reached
        self._buffer.append(record)
        QUEQUE_SIZE.set(len(self._buffer))
        print(
            f"[AIBatcher] Buffered {len(self._buffer)}/{self.batch_size} telemetry records"
        )
        # If we reached capacity, notify loop to flush immediately

        if len(self._buffer) >= self.batch_size:
            self._flush_event.set()  # time to flush

    async def _flush(self):
        """
        Move Buffer to local variable and schedule a processing task.
        This releases the buffer lock quickly so enqueue() is not blocked
        """
        async with self._buffer_lock:
            if not self._buffer:
                # nothing to flush
                self._flush_event.clear()
                return

            batch = self._buffer[:]
            self._buffer.clear()
            QUEQUE_SIZE.set(0)
            self._flush_event.clear()
        print(
            f"[AIBatcher] Flushing batch of {len(batch)} telemetry records for AI analysis..."
        )  # log flush
        # process batch asynchronously under concurrency control
        asyncio.create_task(self._run_with_semaphore(batch))

    async def _run_with_semaphore(self, batch: List[Dict[str, Any]]):
        async with self._semaphore:
            await self._run_batch_with_retries(batch)

    async def _run_batch_with_retries(self, batch: List[Dict[str, Any]]):
        AI_CALLS.inc()
        start = time.time()

        try:
            # 3 attempts with exponential backoff: 1s -> 2s -> 4s
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(3),
                wait=wait_exponential(min=1, max=8),
                retry=retry_if_exception_type(Exception),
                reraise=True,
            ):
                with attempt:
                    await self.analyzer.run_ai_analysis_batch(batch)

            AI_LATENCY.observe(time.time() - start)
        except Exception as exc:
            AI_ERRORS.inc()
            print("[AIBatcher] AI batch failed after retries:", exc)

    async def _batch_loop(self):
        """
        Background loop:
            -wait until flush_event is set or timeout expires
            -then flush
            -repeat while running
        """
        while self._running:
            try:
                # wait_for returns if event_set or times_out(TimeoutError)
                await asyncio.wait_for(
                    self._flush_event.wait(), timeout=self.timeout_seconds
                )
            except asyncio.TimeoutError:
                # timeout expired ;proceed to flush whatever is in buffer
                pass
            await self._flush()
            # small sleep to yield to other coroutines and avoid tight loop
            await asyncio.sleep(0.01)
