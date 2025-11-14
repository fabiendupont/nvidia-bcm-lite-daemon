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


class Process_Sampler_Task(Internal_Sampler_Task):
    def __init__(self, interval: int, offset: int = 0, producer: UUID | None = None, pid=0, process=""):
        super().__init__(interval=interval, offset=offset, producer=producer)
        self._pid = pid
        self._process = process

    def _process_info(self):
        try:
            # TODO : is there a better way?
            from psutil import Process
            from psutil import process_iter

            name = None
            if self._pid > 0:
                pid = self._pid
            elif self._process:
                pid = None
                for proc in process_iter(attrs=["name", "cmdline"]):
                    if (proc.info["name"] == self._process) or (
                        proc.info["cmdline"] and proc.info["cmdline"][0] == self._process
                    ):
                        pid = proc.pid
                        break
                name = self._process
            else:
                pid = os.getpid()
                name = "cm-lite-daemon"
            if pid is None:
                return None, None
            process = Process(pid)
            if name is None and process is not None:
                name = process.name()
            return (name, process)
        except ImportError:
            return None, None

    def initialize(self, now, entity, pool=None, asynchronous=True, follow_up=None):
        definitions = []
        process_name, process_info = self._process_info()
        if process_info is not None:
            definitions += [
                {
                    "producer": self.producer,
                    "measurable": "UserTime",
                    "parameter": process_name,
                    "entity": entity.name,
                    "type": "Process",
                    "unit": "s",
                    "description": "",
                },
                {
                    "producer": self.producer,
                    "measurable": "SystemTime",
                    "parameter": process_name,
                    "entity": entity.name,
                    "type": "Process",
                    "unit": "s",
                    "description": "",
                },
                {
                    "producer": self.producer,
                    "measurable": "ThreadsUsed",
                    "parameter": process_name,
                    "entity": entity.name,
                    "type": "Process",
                    "description": "",
                },
                {
                    "producer": self.producer,
                    "measurable": "VirtualMemoryUsed",
                    "parameter": process_name,
                    "entity": entity.name,
                    "type": "Process",
                    "unit": "B",
                    "description": "",
                },
                {
                    "producer": self.producer,
                    "measurable": "MemoryUsed",
                    "parameter": process_name,
                    "entity": entity.name,
                    "type": "Process",
                    "unit": "B",
                    "description": "",
                },
            ]
        return (True, definitions)

    def sample(self, now, entity, pool=None, asynchronous=True, follow_up=None):
        values = []
        process_name, process_info = self._process_info()
        if process_info is not None:
            now = self._timestamp_in_milliseconds(now)
            cpu_times = process_info.cpu_times()
            threads = len(process_info.threads())
            memory_info = process_info.memory_info()
            values += [
                {
                    "producer": self.producer,
                    "timestamp": now,
                    "measurable": "UserTime",
                    "parameter": process_name,
                    "entity": entity.name,
                    "raw": cpu_times.user,
                    "rate": cpu_times.user,
                },
                {
                    "producer": self.producer,
                    "timestamp": now,
                    "measurable": "SystemTime",
                    "parameter": process_name,
                    "entity": entity.name,
                    "raw": cpu_times.system,
                    "rate": cpu_times.system,
                },
                {
                    "producer": self.producer,
                    "timestamp": now,
                    "measurable": "ThreadsUsed",
                    "parameter": process_name,
                    "entity": entity.name,
                    "raw": threads,
                    "rate": threads,
                },
                {
                    "producer": self.producer,
                    "timestamp": now,
                    "measurable": "VirtualMemoryUsed",
                    "parameter": process_name,
                    "entity": entity.name,
                    "raw": memory_info.vms,
                    "rate": memory_info.vms,
                },
                {
                    "producer": self.producer,
                    "timestamp": now,
                    "measurable": "MemoryUsed",
                    "parameter": process_name,
                    "entity": entity.name,
                    "raw": memory_info.rss,
                    "rate": memory_info.rss,
                },
            ]
        return (True, [Value(it) for it in values])
