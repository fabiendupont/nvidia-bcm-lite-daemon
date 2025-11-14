# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.
#

from __future__ import annotations

import typing

from cm_lite_daemon.monitoring.parser.value import Value
from cm_lite_daemon.monitoring.sampler.internal_sampler_task import Internal_Sampler_Task

if typing.TYPE_CHECKING:
    from uuid import UUID


class MemInfo_Sampler_Task(Internal_Sampler_Task):
    def __init__(self, interval: int, offset: int = 0, producer: UUID | None = None):
        super().__init__(interval=interval, offset=offset, producer=producer)
        self._virtual_memory_info = [
            ("MemoryTotal", "total", "Total system memory", "B"),
            ("MemoryFree", "free", "Free system memory", "B"),
            ("MemoryAvailable", "available", "Available system memory", "B"),
            ("MemoryUsed", "used", "Used system memory", "B"),
            ("BufferMemory", "buffers", "System memory used for buffers", "B"),
            ("CacheMemory", "cached", "System memory used for caching", "B"),
        ]
        self._swap_memory_info = [
            ("SwapTotal", "total", "Total swap memory", "B"),
            ("SwapFree", "free", "Free swap memory", "B"),
            ("SwapUsed", "used", "Used swap memory", "B"),
        ]

    def _memory(self):
        try:
            # TODO : is there a better way?
            from psutil import swap_memory
            from psutil import virtual_memory

            return (virtual_memory(), swap_memory())
        except ImportError:
            return None, None

    def initialize(self, now, entity, pool=None, asynchronous=True, follow_up=None):
        definitions = []
        metrics = set()
        virtual_memory, swap_memory = self._memory()
        for memory, info in [
            (virtual_memory, self._virtual_memory_info),
            (swap_memory, self._swap_memory_info),
        ]:
            if memory is not None:
                for name, item, description, unit in info:
                    if hasattr(memory, item):
                        metrics.add(name)
                        definitions.append(
                            {
                                "producer": self.producer,
                                "measurable": name,
                                "parameter": "",
                                "entity": entity.name,
                                "type": "Memory",
                                "unit": unit,
                                "description": description,
                            }
                        )
        if "MemoryTotal" in metrics and "MemoryAvailable" in metrics:
            definitions.append(
                {
                    "producer": self.producer,
                    "measurable": "MemoryUtilization",
                    "parameter": "",
                    "entity": entity.name,
                    "type": "Memory",
                    "unit": "%",
                    "description": "Percentage of the memory not available",
                }
            )
        return True, definitions

    def sample(self, now, entity, pool=None, asynchronous=True, follow_up=None):
        values = []
        data = {}
        now = self._timestamp_in_milliseconds(now)
        virtual_memory, swap_memory = self._memory()
        for memory, info in [
            (virtual_memory, self._virtual_memory_info),
            (swap_memory, self._swap_memory_info),
        ]:
            if memory is not None:
                for name, item, _, _ in info:
                    try:
                        value = getattr(memory, item)
                        data[name] = value
                        values.append(
                            {
                                "producer": self.producer,
                                "timestamp": now,
                                "measurable": name,
                                "parameter": "",
                                "entity": entity.name,
                                "raw": value,
                                "rate": value,
                            }
                        )
                    except AttributeError:
                        pass
        total = data.get("MemoryTotal", None)
        available = data.get("MemoryAvailable", None)
        if available is not None and bool(total):
            value = (total - available) / total
            values.append(
                {
                    "producer": self.producer,
                    "timestamp": now,
                    "measurable": "MemoryUtilization",
                    "parameter": "",
                    "entity": entity.name,
                    "raw": value,
                    "rate": value,
                }
            )
        return True, [Value(it) for it in values]
