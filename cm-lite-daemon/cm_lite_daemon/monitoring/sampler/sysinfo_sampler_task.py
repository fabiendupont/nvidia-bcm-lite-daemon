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

import os
import typing

from cm_lite_daemon.monitoring.parser.value import Value
from cm_lite_daemon.monitoring.sampler.internal_sampler_task import Internal_Sampler_Task

if typing.TYPE_CHECKING:
    from uuid import UUID


class SysInfo_Sampler_Task(Internal_Sampler_Task):
    def __init__(self, interval: int, offset: int = 0, producer: UUID | None = None):
        super().__init__(interval=interval, offset=offset, producer=producer)

    def _load(self):
        try:
            load = os.getloadavg()
            if not isinstance(load, tuple) or len(load) != 3:
                return None
            return load
        except Exception:
            return None

    def _uptime(self):
        try:
            # TODO : is there a better way?
            from uptime import uptime

            return uptime()
        except ImportError:
            return None

    def _process_count(self):
        try:
            # TODO : is there a better way?
            from psutil import pids

            return len(pids())
        except ImportError:
            return None

    def initialize(self, now, entity, pool=None, asynchronous=True, follow_up=None):
        definitions = []
        if self._load() is not None:
            definitions += [
                {
                    "producer": self.producer,
                    "measurable": "LoadOne",
                    "parameter": "",
                    "entity": entity.name,
                    "type": "OS",
                    "description": "Load average on 1 minute",
                },
                {
                    "producer": self.producer,
                    "measurable": "LoadFive",
                    "parameter": "",
                    "entity": entity.name,
                    "type": "OS",
                    "description": "Load average on 5 minutes",
                },
                {
                    "producer": self.producer,
                    "measurable": "LoadFifteen",
                    "parameter": "",
                    "entity": entity.name,
                    "type": "OS",
                    "description": "Load average on 15 minutes",
                },
            ]
        if self._uptime() is not None:
            definitions += [
                {
                    "producer": self.producer,
                    "measurable": "Uptime",
                    "parameter": "",
                    "entity": entity.name,
                    "type": "Uptime",
                    "cumulative": True,
                    "description": "Uptime",
                }
            ]
        if self._process_count() is not None:
            definitions += [
                {
                    "producer": self.producer,
                    "measurable": "ProcessCount",
                    "parameter": "",
                    "entity": entity.name,
                    "type": "OS",
                    "description": "All processes",
                }
            ]
        return (True, definitions)

    def sample(self, now, entity, pool=None, asynchronous=True, follow_up=None):
        load, uptime, process_count = (
            self._load(),
            self._uptime(),
            self._process_count(),
        )
        now = self._timestamp_in_milliseconds(now)
        values = []
        if load is not None:
            values += [
                {
                    "producer": self.producer,
                    "timestamp": now,
                    "measurable": "LoadOne",
                    "parameter": "",
                    "entity": entity.name,
                    "raw": load[0],
                    "rate": load[0],
                },
                {
                    "producer": self.producer,
                    "timestamp": now,
                    "measurable": "LoadFive",
                    "parameter": "",
                    "entity": entity.name,
                    "raw": load[1],
                    "rate": load[1],
                },
                {
                    "producer": self.producer,
                    "timestamp": now,
                    "measurable": "LoadFifteen",
                    "parameter": "",
                    "entity": entity.name,
                    "raw": load[2],
                    "rate": load[2],
                },
            ]
        if uptime is not None:
            values += [
                {
                    "producer": self.producer,
                    "timestamp": now,
                    "measurable": "Uptime",
                    "parameter": "",
                    "entity": entity.name,
                    "rate": uptime,
                    "raw": int(uptime),
                }
            ]
        if process_count is not None:
            values += [
                {
                    "producer": self.producer,
                    "timestamp": now,
                    "measurable": "ProcessCount",
                    "parameter": "",
                    "entity": entity.name,
                    "raw": process_count,
                    "rate": process_count,
                }
            ]
        return (True, [Value(it) for it in values])
