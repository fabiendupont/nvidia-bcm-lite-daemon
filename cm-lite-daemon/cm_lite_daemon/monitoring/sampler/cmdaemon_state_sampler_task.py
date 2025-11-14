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
from cm_lite_daemon.monitoring.parser.value_interpreter import Value_Interpreter
from cm_lite_daemon.monitoring.sampler.internal_sampler_task import Internal_Sampler_Task

if typing.TYPE_CHECKING:
    from uuid import UUID


class CMDaemon_State_Sampler_Task(Internal_Sampler_Task):
    def __init__(self, cmdaemon, interval: int, offset: int = 0, producer: UUID | None = None):
        super().__init__(interval=interval, offset=offset, producer=producer)
        self._cmdaemon = cmdaemon

    def initialize(self, now, entity, pool=None, asynchronous=True, follow_up=None):
        definitions = [
            {
                "producer": self.producer,
                "measurable": "ManagedServicesOk",
                "entity": entity.name,
                "parameter": "",
                "type": "Internal",
                "range": {"type": "HealthCheck"},
            }
        ]
        return True, definitions

    def sample(self, now, entity, pool=None, asynchronous=True, follow_up=None):
        failed = self._cmdaemon.failed_services()
        value = Value_Interpreter.FAIL_VALUE if bool(failed) else Value_Interpreter.PASS_VALUE
        values = [
            {
                "producer": self.producer,
                "timestamp": int(now * 1000),
                "measurable": "ManagedServicesOk",
                "entity": entity.name,
                "parameter": "",
                "info": ", ".join(failed),
                "rate": value,
                "raw": value,
            }
        ]
        return True, [Value(it) for it in values]
