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

from cm_lite_daemon.monitoring.sample_now_runner import Sample_Now_Runner
from cm_lite_daemon.rpc.ws_request import WS_Request


class Sample_Now:
    def __init__(
        self,
        cmdaemon,
        logger,
        scheduler,
        data_producer_cache,
        enum_value_cache,
        entity_cache,
        measurable_cache,
        last_raw_data_cache,
    ):
        self._cmdaemon = cmdaemon
        self._logger = logger
        self._scheduler = scheduler
        self._data_producer_cache = data_producer_cache
        self._enum_value_cache = enum_value_cache
        self._entity_cache = entity_cache
        self._measurable_cache = measurable_cache
        self._last_raw_data_cache = last_raw_data_cache
        self._runners = []
        self._condition = threading.Condition()

    def do_maintenance(self):
        with self._condition:
            stopped = sum(it.stop(True) for it in self._runners)
            self._runners = [it for it in self._runners if not it._done]
            self._logger.debug(f"Sample now, do_maintenance, stopped: {stopped}, size: {len(self._runners)}")

    def stop(self):
        with self._condition:
            stopped = sum(it.stop() for it in self._runners)
            self._logger.info(f"Sample now, stop, stopped: {stopped}, size: {len(self._runners)}")
            self._runners = []

    def done(self, runner, tracker, result):
        request = WS_Request(self._cmdaemon._connection)
        request.call("mon", "sample_now_result", [tracker, result])
        done = request.wait()
        if not done:
            self._logger.info(f"Sample now, failed to report: {done}, tracker: {tracker}")
        else:
            self._logger.debug(f"Sample now, reported tracker: {tracker}")
        with self._condition:
            self._runners = [it for it in self._runners if it != runner]

    def sample(self, tracker, request):
        runner = Sample_Now_Runner(
            self._cmdaemon,
            self._logger,
            self._scheduler,
            self._data_producer_cache,
            self._enum_value_cache,
            self,
            self._entity_cache,
            self._measurable_cache,
            self._last_raw_data_cache,
            tracker,
            request,
        )
        with self._condition:
            result = runner.start()
            if result:
                self._runners.append(runner)
                self._logger.debug(f"Sample now, started, size: {len(self._runners)}")
        return result
