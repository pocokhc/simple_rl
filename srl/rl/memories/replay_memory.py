import random
from dataclasses import dataclass
from typing import Any

from srl.base.rl.memory import IPriorityMemory


@dataclass
class ReplayMemory(IPriorityMemory):
    capacity: int = 100_000

    def __post_init__(self):
        self.init()

    def init(self):
        self.memory = []
        self.idx = 0

    def add(self, batch: Any, priority=None):
        if len(self.memory) < self.capacity:
            self.memory.append(batch)
        else:
            self.memory[self.idx] = batch
        self.idx += 1
        if self.idx >= self.capacity:
            self.idx = 0

    def update(self, indices, batchs, td_errors) -> None:
        pass

    def sample(self, batch_size, step):
        batchs = random.sample(self.memory, batch_size)
        weights = [1 for _ in range(batch_size)]
        return None, batchs, weights

    def __len__(self) -> int:
        return len(self.memory)

    def backup(self):
        return [
            self.memory,
            self.idx,
        ]

    def restore(self, data):
        self.memory = data[0]
        self.idx = data[1]
        if len(self.memory) > self.capacity:
            self.idx -= len(self.memory) - self.capacity
            if self.idx < 0:
                self.idx = 0
            self.memory = self.memory[-self.capacity :]
        if self.idx >= self.capacity:
            self.idx = 0
