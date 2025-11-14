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

import re
import typing

from cm_lite_daemon.monitoring.parser.value import Value
from cm_lite_daemon.monitoring.sampler.internal_sampler_task import Internal_Sampler_Task

if typing.TYPE_CHECKING:
    from uuid import UUID


class Disk_IO_Sampler_Task(Internal_Sampler_Task):
    def __init__(
        self,
        interval: int,
        offset: int = 0,
        producer: UUID | None = None,
        excludeVirtualDisks: bool = True,
        excludeDisks: list[str] | None = None,
    ):
        super().__init__(interval=interval, offset=offset, producer=producer)
        self.excludeVirtualDisks = excludeVirtualDisks
        self.excludeDisks = []
        self.excludeDisksRegex = []
        if excludeDisks is not None:
            for it in excludeDisks:
                if it[0] == '/' and it[-1] == '/':
                    self.excludeDisksRegex.append(re.compile(it[1:-1]))
                else:
                    self.excludeDisks.append(it)
        self._disk_io_info = (
            ("Reads", "read_count", "Read/s completed successfully", "requests/s"),
            ("MergedReads", "read_merged_count", "Merged reads/s", "requests/s"),
            ("ReadTime", "read_time", "Read time in milliseconds/s", "ms/s"),
            ("Writes", "write_count", "Writes/s completed successfully", "requests/s"),
            ("MergedWrites", "write_merged_count", "Merged writes/s", "requests/s"),
            ("WriteTime", "write_count", "Write time in milliseconds/s", "ms/s"),
        )

    def _io_counters(self) -> list[tuple[str, dict]]:
        try:
            # TODO : is there a better way?
            from psutil import disk_io_counters

            last = None
            io_counters = []
            all_io_counters = sorted([(disk, io) for disk, io in disk_io_counters(perdisk=True).items()])
            for disk, io in all_io_counters:
                if bool(last) and bool(re.match(rf'{last}\d+', disk)):
                    continue
                if self._exclude_disk(disk):
                    continue
                last = disk
                io_counters.append((disk, io))
            return io_counters
        except ImportError:
            return []

    def _exclude_disk(self, disk: str) -> bool:
        if disk in self.excludeDisks:
            return True
        return any(it.match(disk) for it in self.excludeDisksRegex)

    def initialize(self, now, entity, pool=None, asynchronous=True, follow_up=None):
        definitions = []
        for disk, io in self._io_counters():
            for name, item, description, unit in self._disk_io_info:
                if hasattr(io, item):
                    definitions.append(
                        {
                            "producer": self.producer,
                            "measurable": name,
                            "parameter": disk,
                            "entity": entity.name,
                            "type": "Disk",
                            "unit": unit,
                            "description": description,
                        }
                    )
        return True, definitions

    def sample(self, now, entity, pool=None, asynchronous=True, follow_up=None):
        now = self._timestamp_in_milliseconds(now)
        values = []
        for disk, io in self._io_counters():
            for name, item, _, _ in self._disk_io_info:
                value = getattr(io, item, None)
                if value is not None:
                    derivative = self._cummulative(name, disk, now, value)
                    values.append(
                        {
                            "producer": self.producer,
                            "timestamp": now,
                            "measurable": name,
                            "parameter": disk,
                            "entity": entity.name,
                            "raw": value,
                            "rate": derivative,
                        }
                    )
        return True, [Value(it) for it in values]
