from collections import deque
from typing import Dict,Any

class TelemetryQueue:
    def __init__(self):
        self.queue=deque()

    def enqueue(self,packet:Dict[str,Any]):
        self.queue.append(packet)

    def dequeue(self) -> Dict[str,Any]:
        if not self.queue:
            return None

        packet=self.queue.popleft()
        return packet
    
    def size(self) -> int:
        return len(self.queue)

    def isEmpty(self) -> bool:
        return len(self.queue) == 0