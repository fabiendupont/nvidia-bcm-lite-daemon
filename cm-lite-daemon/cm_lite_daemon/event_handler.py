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

import sys


class Event_Handler:
    def __init__(self, logger):
        self._logger = logger
        self._cmdaemon = None

    def set_cmdaemon(self, cmdaemon):
        self._cmdaemon = cmdaemon

    def handle(self, events):
        good = True
        for event in events:
            child_type = event.get("childType", None)
            if child_type is not None:
                self._logger.debug(f"Received event {child_type}")
                handler = f"_handle_{child_type}"
                try:
                    handler = getattr(self, handler)
                    good = good and handler(event)
                except AttributeError as e:
                    self._logger.info(f"Unhandled event {child_type} ({e})")
                except Exception:
                    self._cmdaemon.report_error(sys.exc_info())
            else:
                self._logger.info("Received event without childType")
        self._logger.debug(f"Handled: {len(events)} events, good: {good}")
        return good

    def _handle_EndOfSessionEvent(self, event):
        return self._cmdaemon.end_session(event["reason"])

    def _handle_DevStatusChangedEvent(self, event):
        if "devId" in event and "status" in event:
            return self._cmdaemon.remote_update_status(event["devId"], event["status"])
        return False

    def _handle_EntitiesChangedEvent(self, event):
        type_name = event.get("entityTypeName", "undefined")
        if type_name == "MonitoringDataProducer":
            return self._cmdaemon._monitoring_controller._data_producer_cache.update_remove(
                event.get("updateUuids", []), event.get("removeUuids", [])
            )
        self._logger.info(f"Bad {type_name} changed event")
        return False
