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

from multiprocessing.pool import ApplyResult

from cm_lite_daemon.monitoring.task_output_processor import Task_Output_Processor
from cm_lite_daemon.monitoring.task_service import Task_Service


class Task_Sampler(Task_Service):
    def __init__(
        self,
        cmdaemon,
        logger,
        scheduler,
        enum_value_cache=None,
        translator=None,
        task_initializer=None,
    ):
        super().__init__(cmdaemon, logger, scheduler, "Sampler")
        self._initialized = dict()
        self._translator = translator
        self._task_initializer = task_initializer
        self._output_processor = Task_Output_Processor(
            cmdaemon=self._cmdaemon,
            logger=self._logger,
            enum_value_cache=enum_value_cache,
            translator=self._translator,
        )

    def _get_todo(self):
        (now, timeout, todo) = super()._get_todo()
        if len(self._samplers):
            if (self._task_initializer is None) or (self._task_initializer._last > 0):
                sampler_wait = [(it, it.wait(now, self._last)) for it in self._samplers if len(it.entities) > 0]
                if len(sampler_wait):
                    todo = [it[0] for it in sampler_wait if it[1] == 0]
                    timeout = min([it[1] for it in sampler_wait])
            else:
                timeout = 10
        return (now, timeout, todo)

    def _start(self, now, todo):
        started = [
            it.sample(now, jt, self._scheduler.pool, follow_up=self._output_processor.process)
            for it in todo
            for jt in it.entities
        ]
        count = sum([1 for it in started if isinstance(it[0], ApplyResult) or it[0]])
        values = [it for jt in started for it in jt[1]]
        if len(values) > 0:
            self._logger.debug(f"Direct values: {len(values)}")
            self._translator.push(values)
        return (count, len(todo))
