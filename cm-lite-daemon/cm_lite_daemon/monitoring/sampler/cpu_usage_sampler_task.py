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


class CPU_Usage_Sampler_Task(Internal_Sampler_Task):
    def __init__(
        self, interval: int, offset: int = 0, producer: UUID | None = None, per_cpu=False, normalize_total=True
    ):
        super().__init__(interval=interval, offset=offset, producer=producer)
        self._jiffie = 100
        self._per_cpu = per_cpu
        self._normalize_total = normalize_total
        self._cpu_usage_info = [
            ("CPUUser", "user", "CPU time spent in user mode", "Jiffies"),
            ("CPUNice", "nice", "CPU time spent in nice mode", "Jiffies"),
            ("CPUSystem", "system", "CPU time spent in system mode", "Jiffies"),
            ("CPUIdle", "idle", "CPU time spent in idle mode", "Jiffies"),
            ("CPUWait", "wait", "CPU time spent in I/O wait mode", "Jiffies"),
            ("CPUIrq", "irq", "CPU time spent in servicing irq", "Jiffies"),
            (
                "CPUSoftIrq",
                "softirq",
                "CPU time spent in servicing soft irq",
                "Jiffies",
            ),
            ("CPUSteal", "steal", "CPU time spent in steal mode", "Jiffies"),
            ("CPUGuest", "guest", "CPU time spent in guest mode", "Jiffies"),
        ]

    def _usage(self):
        try:
            # TODO : is there a better way?
            from psutil import cpu_count
            from psutil import cpu_times

            if self._per_cpu:
                return [(str(index), times, 1) for (index, times) in enumerate(cpu_times(percpu=self._per_cpu))]
            else:
                if self._normalize_total:
                    normalize = cpu_count()
                else:
                    normalize = 1
                return [("", cpu_times(), normalize)]
        except ImportError:
            return None

    def initialize(self, now, entity, pool=None, asynchronous=True, follow_up=None):
        definitions = []
        usage = self._usage()
        if usage is not None:
            for cpu_index, cpu_times, _ in usage:
                for name, item, description, unit in self._cpu_usage_info:
                    if hasattr(cpu_times, item):
                        definitions.append(
                            {
                                "producer": self.producer,
                                "measurable": name,
                                "parameter": cpu_index,
                                "entity": entity.name,
                                "type": "CPU",
                                "cumulative": True,
                                "unit": unit,
                                "description": description,
                            }
                        )
            definitions.append(
                {
                    "producer": self.producer,
                    "measurable": "CPUUsage",
                    "parameter": "",
                    "entity": entity.name,
                    "type": "CPU",
                    "cumulative": False,
                    "unit": "%",
                    "description": "Percentage of CPU time not spent in idle mode",
                }
            )
        return (True, definitions)

    def sample(self, now, entity, pool=None, asynchronous=True, follow_up=None):
        values = []
        usage = self._usage()
        if usage is not None:
            now = self._timestamp_in_milliseconds(now)
            for cpu_index, cpu_times, normalize in usage:
                for name, item, _, _ in self._cpu_usage_info:
                    try:
                        value = self._jiffie * getattr(cpu_times, item) / normalize
                        values.append(
                            {
                                "producer": self.producer,
                                "timestamp": now,
                                "measurable": name,
                                "parameter": cpu_index,
                                "entity": entity.name,
                                "raw": int(value),
                                "rate": value,
                            }
                        )
                    except AttributeError:
                        pass
        return (True, [Value(it) for it in values])
