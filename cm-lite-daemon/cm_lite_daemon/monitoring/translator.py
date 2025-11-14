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

from cm_lite_daemon.monitoring.post_cumulative import PostCumulative
from cm_lite_daemon.monitoring.task_service import Task_Service


class Translator(Task_Service):
    def __init__(
        self,
        cmdaemon,
        logger,
        scheduler,
        cache,
        entity_cache,
        measurable_cache,
        last_raw_data_cache=None,
        update_last_raw_data_cache=True,
    ):
        super().__init__(cmdaemon, logger, scheduler, "Translator")
        self._cache = cache
        self._entity_cache = entity_cache
        self._measurable_cache = measurable_cache
        self._last_raw_data_cache = last_raw_data_cache
        self._update_last_raw_data_cache = update_last_raw_data_cache
        self._todo = []
        self._post_cumulative = PostCumulative(measurable_cache)

    def update(self, samplers):
        self._condition.acquire()
        self._condition.notify()
        self._condition.release()

    def push(self, parsed_value):
        self._condition.acquire()
        if isinstance(parsed_value, list):
            self._todo += parsed_value
            n = len(parsed_value)
        else:
            self._todo.append(parsed_value)
            n = 1
        if n > 0:
            self._condition.notify()
        self._logger.debug(f"{self._name}, push {int(n)} / {len(self._todo)}")
        self._condition.release()
        return n

    def _process(self, parsed_value):
        entity = self._entity_cache.find(parsed_value.entity)
        if entity is None:
            return (None, parsed_value)
        measurable = self._measurable_cache.find(parsed_value.measurable, parsed_value.parameter)
        if measurable is None:
            return (None, parsed_value)
        elif measurable.cumulative and self._last_raw_data_cache is not None:
            rate = self._last_raw_data_cache.calculate_rate(
                entity.uuid,
                measurable.uuid,
                parsed_value.timestamp,
                parsed_value.raw,
                self._update_last_raw_data_cache,
            )
        else:
            rate = parsed_value.rate
        self._post_cumulative.process(entity, measurable, parsed_value.timestamp, rate)
        return (
            {
                "entity": entity.uuid,
                "measurable": measurable.uuid,
                "timestamp": parsed_value.timestamp,
                "value": rate,
                "raw": parsed_value.raw,
                "info": parsed_value.info,
                "severity": parsed_value.severity,
            },
            None,
        )

    def _get_todo(self):
        (now, timeout, todo) = super()._get_todo()
        todo = [self._process(it) for it in self._todo]
        self._todo = [it[1] for it in todo if it[1] is not None]
        todo = [it[0] for it in todo if it[0] is not None] + self._post_cumulative.get()
        if len(todo):
            timeout = 0
        return (now, timeout, todo)

    def _start(self, now, todo):
        count = self._cache.push(todo)
        return (count, len(todo))
