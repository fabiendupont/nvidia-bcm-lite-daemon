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


class Measurable_Broker(Task_Service):
    def __init__(self, cmdaemon, logger, scheduler, measurable_cache):
        super().__init__(cmdaemon, logger, scheduler, "Broker")
        self._measurable_cache = measurable_cache
        self._todo = []

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
            n = 1
            self._todo.append(parsed_value)
        if n > 0:
            self._condition.notify()
        self._logger.debug(f"{self._name}, push {int(n)} / {len(self._todo)}")
        self._condition.release()
        return n

    def _get_todo(self):
        now, timeout, todo = super()._get_todo()
        if len(self._todo):
            todo, self._todo = self._todo, []
            timeout = 0
        return now, timeout, todo

    def _start(self, now, todo):
        self._condition.release()
        request = WS_Request(self._cmdaemon._connection)
        request.call("mon", "newMeasurable", [todo])
        new_uuids = request.wait()
        if new_uuids is None:
            self._logger.info(f"{self._name}, rpc error: {request.error()}")
        else:
            self._logger.info(f"{self._name}, rpc {len(new_uuids)} / {len(todo)}")
        self._condition.acquire()
        return len(new_uuids), len(todo)
