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


import datetime
import sys
import threading
import time


class Task_Service:
    DEFAULT_TIMEOUT = 3600

    def __init__(self, cmdaemon, logger, scheduler, name="Service"):
        self._cmdaemon = cmdaemon
        self._logger = logger
        self._scheduler = scheduler
        self._name = name
        self._last = 0
        self._debug = 0
        self._running = False
        self._thread = None
        self._samplers = []
        self._condition = threading.Condition()

    def debug(self, level: int) -> int:
        if self._debug != level:
            self._debug = level
            for sampler in self._samplers:
                sampler.debug = level > 0
            return True
        return False

    def start(self):
        if self._running:
            return False
        self._running = True
        self._logger.debug(f"{self._name} start")
        self._thread = threading.Thread(target=self._run)
        self._thread.daemon = True
        self._thread.start()
        return True

    def update(self, samplers):
        self._condition.acquire()
        self._samplers = samplers
        self._condition.notify()
        self._condition.release()

    def stop(self):
        self._logger.info(f"{self._name} stop")
        if self._thread is not None:
            self._condition.acquire()
            self._running = False
            self._condition.notify()
            self._condition.release()
            self._thread.join()
            self._thread = None
            return True
        return False

    def _now(self):
        now = datetime.datetime.now()
        return time.mktime(now.timetuple()) + now.microsecond / 1000000.0

    def _start(self, now, todo):
        return (0, 0)

    def _run(self):
        self._last = 0
        self._condition.acquire()
        while self._running:
            self._run_once()
        self._condition.release()

    def _run_once(self, wait=True):
        started = None
        try:
            (now, timeout, todo) = self._get_todo()
            if len(todo) == 0:
                self._logger.debug(f"{self._name}, run timeout {timeout:.3f}")
                if wait:
                    self._condition.wait(timeout)
            else:
                started, count = self._start(now, todo)
                self._logger.debug(f"{self._name}, run started {int(started)} / {int(count)}")
                self._last = now
        except Exception:
            self._cmdaemon.report_error(sys.exc_info())
        return started

    def _get_todo(self):
        return (self._now(), self.DEFAULT_TIMEOUT, [])
