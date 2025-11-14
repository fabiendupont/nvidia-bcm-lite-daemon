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
import threading
import time
from multiprocessing.pool import ApplyResult
from uuid import UUID

from cm_lite_daemon.monitoring.cache import Cache
from cm_lite_daemon.monitoring.data_producer_cache import DataProducer_Cache
from cm_lite_daemon.monitoring.task_output_processor import Task_Output_Processor
from cm_lite_daemon.monitoring.translator import Translator


class Sample_Now_Runner:
    def __init__(
        self,
        cmdaemon,
        logger,
        scheduler,
        data_producer_cache,
        enum_value_cache,
        sample_now,
        entity_cache,
        measurable_cache,
        last_raw_data_cache,
        tracker,
        request,
    ):
        self._cmdaemon = cmdaemon
        self._logger = logger
        self._scheduler = scheduler
        self._data_producer_cache = data_producer_cache
        self._sample_now = sample_now
        self._entity_cache = entity_cache
        self._measurable_cache = measurable_cache
        self._last_raw_data_cache = last_raw_data_cache
        self._cache = Cache(self._logger)
        self._translator = Translator(
            self._cmdaemon,
            self._logger,
            self._scheduler,
            self._cache,
            self._entity_cache,
            self._measurable_cache,
            self._last_raw_data_cache,
            False,
        )
        self._output_processor = Task_Output_Processor(
            cmdaemon=self._cmdaemon,
            logger=self._logger,
            enum_value_cache=enum_value_cache,
            translator=self._translator,
        )
        self._tracker = tracker
        self._request = request
        self._result = None
        self._thread = None
        self._condition = threading.Condition()
        self._done = None
        self.__normalize()

    def __normalize(self):
        for name in ['entities', 'measurables']:
            self._request[name] = [UUID(it) for it in self._request[name]]

    def stop(self, check: bool = False) -> bool:
        with self._condition:
            if not check or self._done:
                return False
            thread, self._thread = self._thread, None
            self._done = True
            self._condition.notify()
        thread.join()
        return True

    def start(self):
        with self._condition:
            self._done = False
            self._thread = threading.Thread(target=self.__run)
            self._thread.daemon = True
            self._thread.start()
        return True

    def _now(self):
        now = datetime.datetime.now()
        return time.mktime(now.timetuple()) + now.microsecond / 1000000.0

    def __run(self):
        now = self._now()
        # TODO: CM-15861 Multiplexer
        node_uuid = self._cmdaemon.uuid
        entity = self._entity_cache.get(node_uuid)
        samplers = self.__get_samplers()
        started = [
            it.sample(
                now,
                entity,
                self._scheduler.pool,
                follow_up=self._output_processor.process,
            )
            for it in samplers
        ]
        run_async = [it[0] for it in started if isinstance(it[0], ApplyResult)]
        values = [it for jt in started for it in jt[1]]
        if len(values) > 0:
            self._logger.debug(f"Sample now, direct values: {len(values)}")
            self._translator.push(values)
        if len(run_async) > 0:
            self._logger.debug(f"Sample now, wait for: {len(run_async)}")
            list(map(ApplyResult.wait, run_async))
        self.__translate(now)
        self.__done({"node": node_uuid, "uuid": self._tracker["uuid"]})

    def __get_samplers(self):
        producers = self._measurable_cache.producers(self._request["measurables"])
        samplers = self._data_producer_cache.get_samplers(DataProducer_Cache.ON_DEMAND, producers)
        self._logger.info(
            "Sample now, producers: %d, samplers: %d, entities: %d, measurables: %d",
            len(producers),
            len(samplers),
            len(self._request["entities"]),
            len(self._request["measurables"]),
        )
        if self._request.get("debug", False):
            for it in samplers:
                it.debug = True
        return samplers

    def __translate(self, now):
        self._translator._run_once(False)
        entities = set(self._request["entities"])
        measurables = set(self._request["measurables"])
        data = [
            {
                "entity": it["entity"],
                "measurable": it["measurable"],
                "t0": it["timestamp"],
                "t1": it["timestamp"],
                "value": it["value"],
                "now_info": it.get("info", ""),
            }
            for it in self._cache.fetch(True)
            if ((it["entity"] in entities) and (it["measurable"] in measurables))
        ]
        self._logger.info("Sample now, data: %d", len(data))
        self._result = {"timestamp": int(now * 1000), "items": data}

    def __done(self, tracker):
        with self._condition:
            self._done = True
        self._sample_now.done(self, tracker, self._result)
