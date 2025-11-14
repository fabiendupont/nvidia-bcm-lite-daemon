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
import re
import typing

from cm_lite_daemon.monitoring.parser.value import Value
from cm_lite_daemon.monitoring.sampler.internal_sampler_task import Internal_Sampler_Task

if typing.TYPE_CHECKING:
    from uuid import UUID


class Disk_Space_Sampler_Task(Internal_Sampler_Task):
    def __init__(self, interval: int, offset: int = 0, producer: UUID | None = None, excludeMountPoints=None):
        super().__init__(interval=interval, offset=offset, producer=producer)
        if bool(excludeMountPoints):
            self.excludeMountPoints = [it for it in excludeMountPoints if bool(it) and it[0] != "^"]
            self.excludeMountPointsRegex = [re.compile(it) for it in excludeMountPoints if bool(it) and it[0] == "^"]
        else:
            self.excludeMountPoints = []
            self.excludeMountPointsRegex = []

    def _space(self):
        try:
            # TODO : is there a better way?
            from psutil import disk_partitions
            from psutil import disk_usage

            space = []
            for it in disk_partitions():
                if (os.name == "nt") and (("cdrom" in it.opts) or (it.fstype == "")):
                    continue
                if it.mountpoint in self.excludeMountPoints:
                    continue
                if any(jt.match(it.mountpoint) for jt in self.excludeMountPointsRegex):
                    continue
                try:
                    usage = disk_usage(it.mountpoint)
                    space.append((it.mountpoint, usage.used, usage.free))
                except PermissionError:
                    space.append((it.mountpoint, None, None))
            return space
        except ImportError:
            return None

    def initialize(self, now, entity, pool=None, asynchronous=True, follow_up=None):
        definitions = []
        space = self._space()
        if space:
            for mountpoint, _, _ in space:
                definitions.append(
                    {
                        "producer": self.producer,
                        "measurable": "UsedSpace",
                        "parameter": mountpoint,
                        "entity": entity.name,
                        "type": "Disk",
                        "unit": "B",
                        "description": "Used space on the specified mount point",
                    }
                )
                definitions.append(
                    {
                        "producer": self.producer,
                        "measurable": "FreeSpace",
                        "parameter": mountpoint,
                        "entity": entity.name,
                        "type": "Disk",
                        "unit": "B",
                        "description": "Free space on the specified mount point",
                    }
                )
        return (True, definitions)

    def sample(self, now, entity, pool=None, asynchronous=True, follow_up=None):
        values = []
        space = self._space()
        if space:
            now = self._timestamp_in_milliseconds(now)
            for mountpoint, used, free in space:
                values.append(
                    {
                        "producer": self.producer,
                        "timestamp": now,
                        "measurable": "UsedSpace",
                        "parameter": mountpoint,
                        "entity": entity.name,
                        "raw": used,
                        "rate": used,
                    }
                )
                values.append(
                    {
                        "producer": self.producer,
                        "timestamp": now,
                        "measurable": "FreeSpace",
                        "parameter": mountpoint,
                        "entity": entity.name,
                        "raw": free,
                        "rate": free,
                    }
                )
        return (True, [Value(it) for it in values])
