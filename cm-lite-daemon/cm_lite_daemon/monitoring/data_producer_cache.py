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

import threading
from uuid import UUID

from cm_lite_daemon.monitoring.data_producer import DataProducer
from cm_lite_daemon.rpc.ws_request import WS_Request


class DataProducer_Cache:
    TIMED = 1
    ON_DEMAND = 2

    def __init__(self, cmdaemon, controller, logger, connection, data_producers=None):
        self._cmdaemon = cmdaemon
        self._controller = controller
        self._logger = logger
        self._connection = connection
        self._data_producers = [] if data_producers is None else data_producers
        self._running = False
        self._thread = None
        self._completed_threads = []
        self._condition = threading.Condition()
        self._update_uuids = []
        self._remove_uuids = []

    def do_maintenance(self):
        self._condition.acquire()
        [it.join() for it in self._completed_threads]
        self._completed_threads = []
        self._condition.release()

    def size(self):
        self._condition.acquire()
        n = len(self._data_producers)
        self._condition.release()
        return n

    def update(self, data_producers):
        self._condition.acquire()
        self._data_producers = data_producers
        self._condition.release()

    def get_samplers(self, mode=TIMED, selection=None):
        self._condition.acquire()
        samplers = [
            it.get_sampler()
            for it in self._data_producers
            if (((mode == self.ON_DEMAND) or not it.disabled) and ((selection is None) or (it.uuid in selection)))
        ]
        self._condition.release()
        return [it for it in samplers if it is not None]

    def update_remove(self, update_uuids, remove_uuids):
        self._condition.acquire()
        self._update_uuids += [UUID(it) for it in update_uuids]
        self._remove_uuids += [UUID(it) for it in remove_uuids]
        if not self._running:
            self._running = True
            self._thread = threading.Thread(target=self._update_remove)
            self._thread.daemon = True
            self._thread.start()
        self._condition.release()
        return True

    def _update_remove(self):
        updated = None
        remove_uuids = None
        while True:
            self._condition.acquire()
            if bool(remove_uuids):
                old = len(self._data_producers)
                self._data_producers = [it for it in self._data_producers if it.uuid not in remove_uuids]
                self._logger.debug(
                    f"Update data producers, removed: {len(remove_uuids)}, "
                    f"producers: {len(self._data_producers)}, old: {old}"
                )
            if bool(updated):
                old = len(self._data_producers)
                producers = {it.uuid: it for it in self._data_producers}
                updated = [DataProducer(self._cmdaemon, it) for it in updated]
                producers.update({it.uuid: it for it in updated})
                self._data_producers = producers.values()
                self._logger.debug(
                    f"Update data producers, updated: {len(updated)}, "
                    f"producers: {len(self._data_producers)}, old: {old}"
                )
            if bool(self._update_uuids) or bool(self._remove_uuids):
                update_uuids, self._update_uuids = self._update_uuids, []
                remove_uuids, self._remove_uuids = self._remove_uuids, []
            else:
                self._completed_threads.append(self._thread)
                self._running = False
                self._thread = None
                break
            self._condition.release()
            if len(update_uuids):
                self._logger.debug(f"Update data producers, fetch: {len(update_uuids)}")
                request = WS_Request(self._connection)
                request.call("mon", "getMonitoringDataProducersByUuids", [update_uuids])
                updated = request.wait()
            else:
                updated = None
        self._condition.release()
        self._controller.update()
        return True
