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

from cm_lite_daemon.monitoring.sampler.sampler_task import Sampler_Task
from cm_lite_daemon.monitoring.sampler.script_runner import Script_Runner

if typing.TYPE_CHECKING:
    from uuid import UUID


class Script_Sampler_Task(Sampler_Task):
    def __init__(
        self,
        cmdaemon,
        interval: int,
        script: str,
        producer: UUID | None = None,
        timeout: int = 15,
        name: str | None = None,
        arguments: list[str] | None = None,
        offset: int = 0,
        format=None,
    ):
        super().__init__(interval, offset, producer)
        self._cmdaemon = cmdaemon
        self.script = script
        self.timeout = timeout
        self.name = name
        self.arguments = [] if arguments is None else arguments
        self.runner = None
        self._format = format

    def run(self, now, last=None):
        if self.runner and self.runner.done is None:
            return False
        return super().run(now, last)

    def need_reinitialize(self, other):
        return (self.script != other.script) or (self.arguments != other.arguments) or (self._format != other._format)

    def initialize(self, now, entity, pool=None, asynchronous=True, follow_up=None):
        return self.start(now, entity, pool, asynchronous, ["--initialize"], follow_up=follow_up)

    def sample(self, now, entity, pool=None, asynchronous=True, follow_up=None):
        return self.start(now, entity, pool, asynchronous, follow_up=follow_up)

    def start(
        self,
        now,
        entity,
        pool=None,
        asynchronous=True,
        extra_arguments=None,
        follow_up=None,
    ):
        if self.runner and self.runner.done is None:
            return (False, [])
        environment = {}
        if self.debug:
            environment["CMD_DEBUG"] = "1"
        if extra_arguments is None:
            extra_arguments = []
        if entity is not None:
            if entity.environment is not None:
                environment.update(entity.environment)
        self.runner = Script_Runner(
            cmdaemon=self._cmdaemon,
            command=self.script,
            arguments=extra_arguments + self.arguments,
            env=environment,
            pool=pool,
            timeout=self.timeout,
            follow_up=follow_up,
            follow_up_args=[
                self.producer,
                self._format,
                now,
                entity,
                self.name,
                self.arguments,
            ],
        )
        return self.runner.run(asynchronous), []

    def data(self):
        if self.runner is None:
            return None
        elif self.runner.done is None:
            return None
        return self.runner.output

    def info(self):
        if self.runner is None:
            return None
        elif self.runner.done is None:
            return None
        return self.runner.info
