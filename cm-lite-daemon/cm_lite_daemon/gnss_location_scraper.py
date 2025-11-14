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


import json
import os
import threading

from cm_lite_daemon.monitoring.sampler.script_runner import Script_Runner
from cm_lite_daemon.rpc.ws_request import WS_Request


class GNSSLocationScraper:
    def __init__(
        self,
        cmdaemon,
        logger,
        connection,
        script="/cm/shared/cm-gnss.py",
        interval=3600,
        timeout=15,
    ):
        self._cmdaemon = cmdaemon
        self._logger = logger
        self._connection = connection
        self._thread = None
        self._condition = threading.Condition()
        self.script = script
        self.interval = interval
        self.timeout = timeout

    def start(self):
        self._condition.acquire()
        if self._thread is not None and self._needed():
            self._thread = threading.Thread(target=self._run)
            self._thread.daemon = True
            self._thread.start()
            self._logger.info("GNSS location scraper started")
        self._condition.release()

    def stop(self):
        thread = None
        self._condition.acquire()
        if self._thread is not None:
            thread, self._thread = self._thread, thread
            self._condition.notify()
        self._condition.release()
        if thread:
            thread.join()
            self._logger.info("GNSS location scraper stopped")

    def _needed(self):
        return os.path.exists(self.script)

    def __run(self):
        self._condition.acquire()
        while not self._thread:
            self._update_location()
            self._starting_condition.wait(self.interval)
        self._condition.release()

    def _update_location(self):
        try:
            runner = Script_Runner(self._cmdaemon, self.script, env=self._cmdaemon._environment, timeout=self.timeout)
            if runner.run(False):
                locations = json.loads(runner.output)
                for location in locations:
                    # TODO: add support for sub entities? should not be needed
                    location["ref_entity_uuid"] = self._cmdaemon.uuid
                request = WS_Request(self._connection)
                request.call("part", "setGNSSLocations", [locations])
                changed = request.wait()
                self._logger.info("GNSS location scraper updated location, changed: %d", changed)
            else:
                self._logger.info("GNSS location scraper failed to run")
        except Exception as e:
            self._logger.info("GNSS location scraper, error: %s", e)
