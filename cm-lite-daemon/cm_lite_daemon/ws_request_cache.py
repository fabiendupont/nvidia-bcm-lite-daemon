#
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
import threading


class WS_Request_Cache:
    def __init__(self, handler, logger):
        self._handler = handler
        self._logger = logger
        self._cmdaemon = None
        self._cache = dict()
        self._condition = threading.Condition()

    def set_cmdaemon(self, cmdaemon):
        self._cmdaemon = cmdaemon

    def push(self, request):
        with self._condition:
            self._cache[request._uuid] = request
            self._logger.debug(f"Push request {request._uuid}, size: {len(self._cache)}")
            return True

    def failed(self, request):
        with self._condition:
            del self._cache[request._uuid]
            self._logger.debug(f"Failed request {request._uuid}, size: {len(self._cache)}")
            return True

    def has(self, uuid):
        with self._condition:
            return uuid in self._cache

    def get(self, uuid, remove=False):
        with self._condition:
            if uuid in self._cache:
                result = self._cache[uuid]
                if remove:
                    del self._cache[uuid]
                self._logger.debug(f"Get request {uuid}, remove: {remove}, size: {len(self._cache)}")
                return result
            if bool(self._cache):
                self._logger.info(f"Get request {uuid} not found, size {len(self._cache)}")
        return None

    def data(self, jsondata):
        self._logger.debug(f"Request data: {len(jsondata)}")
        try:
            data = json.loads(jsondata)
        except json.decoder.JSONDecodeError as e:
            self._logger.warning(f"Failed to parse message: {str(e)}")
            self._logger.info(jsondata)
            return False
        if not isinstance(data, dict):
            self._logger.warning("No dict in message")
            self._logger.info(jsondata)
            return False
        if "uuid" not in data:
            self._logger.warning("No UUID in message")
            self._logger.info(jsondata)
            return False
        error = False
        uuid = data["uuid"]
        if "errormessage" in data:
            error = True
            self._logger.warning(f"Error message: {data['errormessage']}")
        elif "data" not in data:
            self._logger.warning("No data in message")
            self._logger.debug(data)
            return False
        else:
            data = data["data"]
        request = self.get(uuid, True)
        if request is None:
            if error:
                self._logger.debug(f"New request {uuid} with error: {data}")
                return False
            self._logger.debug(f"Handle new request {uuid} data: {len(data)}")
            return self._handler.handle(uuid, data)
        self._logger.debug(f"Fill existing request {uuid} data: {len(jsondata)}")
        return request.data(data)
