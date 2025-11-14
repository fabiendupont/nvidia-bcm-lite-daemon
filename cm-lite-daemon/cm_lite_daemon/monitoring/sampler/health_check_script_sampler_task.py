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

from cm_lite_daemon.monitoring.parser.text_typer import Text_Typer
from cm_lite_daemon.monitoring.sampler.script_sampler_task import Script_Sampler_Task

if typing.TYPE_CHECKING:
    from uuid import UUID


class Health_Check_Script_Sampler_Task(Script_Sampler_Task):
    def __init__(
        self,
        cmdaemon,
        interval: int,
        script: str,
        producer: UUID | None = None,
        timeout: int = 15,
        arguments: list[str] | None = None,
        offset: int = 0,
        name: str = "",
        description: str = "",
        typeClass: str = "",
    ):
        super().__init__(
            cmdaemon,
            interval,
            script,
            producer,
            timeout,
            name,
            arguments,
            offset,
            Text_Typer.CHECK,
        )
        self.description = description
        self.typeClass = typeClass

    def need_reinitialize(self, other):
        return False

    def initialize(self, now, entity, pool=None, asynchronous=True, follow_up=None):
        definition = {
            "producer": self.producer,
            "measurable": self.name,
            "parameter": " ".join(self.arguments),
            "entity": entity.name,
            "type": self.typeClass,
            "description": self.description,
            "range": {"type": "HealthCheck"},
        }
        return (True, [definition])
