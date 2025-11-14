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

from uuid import UUID

from cm_lite_daemon.monitoring.sampler.task import Task


class Sampler_Task(Task):
    def __init__(self, interval: int, offset: int = 0, producer: UUID | None = None):
        super().__init__(interval, offset)
        if producer is None:
            self.producer = UUID(int=0)
        else:
            self.producer = producer
        self.entities = []
        self.last = dict()
        self.debug = False

    def start(self, now, entity, pool=None, asynchronous=True):
        return (False, [])

    def data(self):
        return None

    def need_reinitialize(self, other):
        return False

    def _cummulative(self, measurable, parameter, timestamp, value):
        derivative = None
        old_timestamp, old_value = self.last.get((measurable, parameter), (None, None))
        if old_timestamp is not None:
            if old_value is not None or timestamp > old_timestamp:
                derivative = 1000.0 * (value - old_value) / (timestamp - old_timestamp)
        self.last[(measurable, parameter)] = (timestamp, value)
        return derivative
