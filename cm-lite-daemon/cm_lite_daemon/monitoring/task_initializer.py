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

from cm_lite_daemon.monitoring.initialized import Initialized
from cm_lite_daemon.monitoring.parser.initialize_json import Initialize_JSON
from cm_lite_daemon.monitoring.parser.initialize_text import Initialize_text
from cm_lite_daemon.monitoring.parser.initialize_yaml import Initialize_YAML
from cm_lite_daemon.monitoring.parser.text_typer import Text_Typer
from cm_lite_daemon.monitoring.task_service import Task_Service


class Task_Initializer(Task_Service):
    def __init__(
        self,
        cmdaemon,
        logger,
        scheduler,
        enum_value_cache,
        measurable_broker=None,
        entity_measurable_cache=None,
        source_state_cache=None,
    ):
        super().__init__(cmdaemon, logger, scheduler, "Initializer")
        self._initialized = dict()
        self._enum_value_cache = enum_value_cache
        self._measurable_broker = measurable_broker
        self._entity_measurable_cache = entity_measurable_cache
        self._source_state_cache = source_state_cache

    def update(self, samplers):
        self._condition.acquire()
        samplers.sort(key=lambda it: it.producer)
        i, j = 0, 0
        while (i < len(self._samplers)) and (j < len(samplers)):
            if self._samplers[i].producer < samplers[j].producer:
                uuids = [it.uuid for it in self._samplers[i].entities]
                for uuid in uuids:
                    self._initialized.pop((self._samplers[i].producer, uuid), None)
                i += 1
            elif self._samplers[i].producer > samplers[j].producer:
                j += 1
            else:
                if self._samplers[i].need_reinitialize(samplers[j]):
                    self.reinitialize([self._samplers[i].producer])
                i += 1
                j += 1
        while i < len(self._samplers):
            uuids = [it.uuid for it in self._samplers[i].entities]
            for uuid in uuids:
                self._initialized.pop((self._samplers[i].producer, uuid), None)
            i += 1
        self._samplers = samplers
        self._condition.notify()
        self._condition.release()

    def reinitialize(self, producers=None, entities=None):
        if producers is None and entities is None:
            n = len(self._initialized)
            self._initialized.clear()
            return n
        if producers is None:
            producers = []
        if entities is None:
            entities = []
        if bool(entities):
            n = len([v.clear() for (p, e), v in self._initialized.items() if p in producers and e in entities])
        else:
            n = len([v.clear() for (p, e), v in self._initialized.items() if p in producers])
        return n

    def _get_todo(self):
        now, timeout, todo = super()._get_todo()
        for sampler, entity in ((it, jt) for it in self._samplers for jt in it.entities):
            index = (sampler.producer, entity.uuid)
            if index in self._initialized:
                if self._initialized[index].timestamp > 0:
                    continue
            else:
                self._initialized[index] = Initialized()
            self._initialized[index].done(now)
            todo.append((sampler, entity))
            timeout = 0
        return now, timeout, todo

    def _start(self, now, todo):
        started = [
            sampler.initialize(now, entity, self._scheduler.pool, follow_up=self._process) for sampler, entity in todo
        ]
        count = sum(1 for it in started if isinstance(it[0], ApplyResult) or it[0])
        definitions = [it for jt in started for it in jt[1]]
        if len(definitions) > 0:
            self._logger.debug(f"Direct definitions: {len(definitions)}")
            self._measurable_broker.push(definitions)
            self._entity_measurable_cache.push(definitions)
        self._done_once = True
        return count, len(todo)

    def _process(self, runner, producer, expected_format, now, entity, name=None, arguments=None):
        parser = None
        if runner is not None and runner.output is not None:
            typer = Text_Typer()
            detected_format = typer.determine_format(runner.output, expected_format)
            if detected_format == Text_Typer.TEXT:
                parser = Initialize_text(producer, entity.name, self._enum_value_cache)
            elif detected_format == Text_Typer.JSON:
                parser = Initialize_JSON(producer, entity.name, self._enum_value_cache)
            elif detected_format == Text_Typer.YAML:
                parser = Initialize_YAML(producer, entity.name, self._enum_value_cache)
            else:
                self._logger.debug(
                    f"Unable to determine format for {runner.command} ({producer}) based on {len(runner.output)} bytes"
                )
        if parser is not None:
            definitions = parser.parse(runner.output)
            self._logger.debug(
                f"New definitions: {len(definitions)} based on {len(runner.output)} bytes (type: {detected_format})"
            )
            self._measurable_broker.push(definitions)
            self._entity_measurable_cache.push(definitions)
