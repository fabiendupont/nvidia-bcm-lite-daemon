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

from cm_lite_daemon.monitoring.task_service import Task_Service
from cm_lite_daemon.rpc.ws_request import WS_Request


class Entity_Measurable_Cache(Task_Service):
    def __init__(self, cmdaemon, logger, scheduler, entity_cache, measurable_cache):
        super().__init__(cmdaemon, logger, scheduler, "Entity measurable cache")
        self.entity_cache = entity_cache
        self.measurable_cache = measurable_cache
        self._known = set()
        self._todo = set()

    def update(self, samplers):
        self._condition.acquire()
        self._condition.notify()
        self._condition.release()

    def push(self, definition):
        self._condition.acquire()
        if isinstance(definition, list):
            add = [(it["entity"], it["measurable"], it["parameter"]) for it in definition]
        else:
            add = [
                (
                    definition["entity"],
                    definition["measurable"],
                    definition["parameter"],
                )
            ]
        n = len(self._todo)
        self._todo.update([it for it in add if it not in self._known])
        n = len(self._todo) - n
        if n > 0:
            self._condition.notify()
        self._logger.debug(f"{self._name}, push {int(n)} / {len(self._todo)}, added: {len(add)}")
        self._condition.release()
        return n

    def _process(self, item):
        entity = self.entity_cache.find(item[0])
        if entity is None:
            return (None, item, None)
        measurable = self.measurable_cache.find(item[1], item[2])
        if measurable is None:
            return (None, item, None)
        return (item, None, (entity.uuid, measurable.uuid))

    def _get_todo(self):
        (now, timeout, todo) = super()._get_todo()
        todo = [self._process(it) for it in self._todo]
        self._todo = set([it[1] for it in todo if it[1] is not None])
        self._known.update([it[0] for it in todo if it[0] is not None])
        todo = [it[2] for it in todo if it[2] is not None]
        if len(todo):
            timeout = 0
        return (now, timeout, todo)

    def _start(self, now, todo):
        self._condition.release()
        request = WS_Request(self._cmdaemon._connection)
        entities = [it[0] for it in todo]
        measurables = [it[1] for it in todo]
        request.call("mon", "addEntityMeasurable", [entities, measurables])
        added = request.wait()
        if added is None:
            self._logger.debug(f"{self._name}, rpc error: {request.error()}")
        else:
            self._logger.debug(f"{self._name}, rpc {int(added)} / {len(todo)}")
        self._condition.acquire()
        return (added, len(todo))
