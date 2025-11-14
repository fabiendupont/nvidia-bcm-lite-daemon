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
import time

from cm_lite_daemon.monitoring.cache import Cache
from cm_lite_daemon.monitoring.data_producer import DataProducer
from cm_lite_daemon.monitoring.data_producer_cache import DataProducer_Cache
from cm_lite_daemon.monitoring.entity import Entity
from cm_lite_daemon.monitoring.entity_cache import Entity_Cache
from cm_lite_daemon.monitoring.entity_measurable_cache import Entity_Measurable_Cache
from cm_lite_daemon.monitoring.enum_value_cache import Enum_Value_Cache
from cm_lite_daemon.monitoring.last_raw_data_cache import Last_Raw_Data_Cache
from cm_lite_daemon.monitoring.measurable import Measurable
from cm_lite_daemon.monitoring.measurable_broker import Measurable_Broker
from cm_lite_daemon.monitoring.measurable_cache import Measurable_Cache
from cm_lite_daemon.monitoring.sample_now import Sample_Now
from cm_lite_daemon.monitoring.source_state_cache import Source_State_Cache
from cm_lite_daemon.monitoring.task_initializer import Task_Initializer
from cm_lite_daemon.monitoring.task_sampler import Task_Sampler
from cm_lite_daemon.monitoring.translator import Translator
from cm_lite_daemon.rpc.ws_request import WS_Request


class Controller:
    def __init__(self, cmdaemon, logger, scheduler, connection):
        self._debug = 0
        self._cmdaemon = cmdaemon
        self._logger = logger
        self._scheduler = scheduler
        self._connection = connection
        self._cache = Cache(self._logger)
        self._entity_cache = Entity_Cache()
        self._measurable_cache = Measurable_Cache()
        self._enum_value_cache = Enum_Value_Cache()
        self._measurable_broker = Measurable_Broker(
            self._cmdaemon, self._logger, self._scheduler, self._measurable_cache
        )
        self._source_state_cache = Source_State_Cache()
        self._data_producer_cache = DataProducer_Cache(self._cmdaemon, self, self._logger, self._connection)
        self._last_raw_data_cache = Last_Raw_Data_Cache()
        self._entity_measurable_cache = Entity_Measurable_Cache(
            self._cmdaemon,
            self._logger,
            self._scheduler,
            self._entity_cache,
            self._measurable_cache,
        )
        self._translator = Translator(
            self._cmdaemon,
            self._logger,
            self._scheduler,
            self._cache,
            self._entity_cache,
            self._measurable_cache,
            self._last_raw_data_cache,
        )
        self._task_initializer = Task_Initializer(
            self._cmdaemon,
            self._logger,
            self._scheduler,
            self._enum_value_cache,
            self._measurable_broker,
            self._entity_measurable_cache,
            self._source_state_cache,
        )
        self._task_sampler = Task_Sampler(
            self._cmdaemon,
            self._logger,
            self._scheduler,
            self._enum_value_cache,
            self._translator,
            self._task_initializer,
        )
        self._sample_now = Sample_Now(
            self._cmdaemon,
            self._logger,
            self._scheduler,
            self._data_producer_cache,
            self._enum_value_cache,
            self._entity_cache,
            self._measurable_cache,
            self._last_raw_data_cache,
        )
        self._all_services = [
            self._task_initializer,
            self._task_sampler,
            self._translator,
            self._entity_measurable_cache,
            self._measurable_broker,
        ]

    def initialize(self):
        self._logger.info("Monitoring initialize")
        request_entities = WS_Request(self._connection)
        request_entities.call("mon", "getLiteMonitoredEntities")

        request_measurables = WS_Request(self._connection)
        request_measurables.call("mon", "getLiteMonitoringMeasurables")

        request_producers = WS_Request(self._connection)
        request_producers.call("mon", "getMonitoringDataProducers")

        entities = request_entities.wait()
        if entities is None:
            self._logger.warning("Unable to load entities")
            return False
        entities = [Entity(it) for it in entities]
        self._logger.info(f"Loaded {len(entities)} entities")

        measurables = request_measurables.wait()
        if measurables is None:
            self._logger.warning("Unable to load measurables")
            return False
        measurables = [Measurable(it) for it in measurables]
        self._logger.info(f"Loaded {len(measurables)} measurables")

        producers = request_producers.wait()
        if producers is None:
            self._logger.warning("Unable to load entities")
            return False
        producers = [DataProducer(self._cmdaemon, it) for it in producers]
        self._logger.info(f"Loaded {len(producers)} producers")

        self._entity_cache.update(entities)
        self._measurable_cache.update(measurables)
        self._data_producer_cache.update(producers)
        self._last_raw_data_cache.update(measurables)
        return len(entities) > 0

    def _debug(self, level: int) -> int:
        return sum(it.debug(level) for it in self._all_services)

    def start(self):
        n = sum(it.start() for it in self._all_services)
        self.update()
        return n

    def do_maintenance(self):
        self._sample_now.do_maintenance()

    def update(self):
        entity = self._entity_cache.get(self._cmdaemon.uuid)
        samplers = self._data_producer_cache.get_samplers()
        if entity is not None:
            entity.environment = self._cmdaemon._environment
            # TODO: CM-15861 Multiplexer
            for it in samplers:
                it.entities = [entity]
        else:
            self._logger.info(f"Unable to find monitoring entity {self._cmdaemon.uuid}")
        self._logger.info(f"Update monitoring, samplers {len(samplers)}/{self._data_producer_cache.size()}")
        [it.update(samplers) for it in self._all_services]

    def update_entities_measurables(
        self,
        added_entities,
        updated_entities,
        removed_entities,
        added_measurables,
        updated_measurables,
        removed_measurables,
    ):
        try:
            entity_count = self._entity_cache.changed(added_entities, updated_entities, removed_entities)
            measurable_count = self._measurable_cache.changed(
                added_measurables, updated_measurables, removed_measurables
            )
            self._logger.info(f"Update monitoring, entities: {entity_count}: measurables: {measurable_count}")
            if measurable_count:
                self._last_raw_data_cache.update(self._measurable_cache._measurables)
            self.update()
        except Exception as e:
            self._logger.info(f"Update monitoring failed: {e}")
            self._cmdaemon.report_error(sys.exc_info())

    def sample_now(self, tracker, request):
        return self._sample_now.sample(tracker, request)

    def stop(self):
        n = sum([it.stop() for it in self._all_services])
        self._scheduler.wait()
        return n

    def _now(self):
        now = datetime.datetime.now()
        return time.mktime(now.timetuple()) + now.microsecond / 1000000.0

    def request_quick_pickup(self, priority=25):
        request_entities = WS_Request(self._connection)
        request_entities.call(
            "mon",
            "requestPickupIntervals",
            [
                [
                    {
                        "baseType": "MonitoringPickupInterval",
                        "ref_node_uuid": self._cmdaemon.uuid,
                        "times": 1,
                        "interval": 3,
                        "priority": priority,
                    }
                ]
            ],
        )
