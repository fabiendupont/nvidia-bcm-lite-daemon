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

from __future__ import annotations

import json
import threading
import uuid

from cm_lite_daemon.object_to_json_encoder import Object_To_JSON_Encoder


class WS_Request:
    def __init__(self, connection, timeout: int | None = 60, debug: bool = False):
        self._uuid = None
        self._connection = connection
        self._logger = self._connection._request_cache._logger
        self._timeout = timeout
        self._reply = None
        self._error = None
        self._debug = debug
        self._data_condition = threading.Condition()

    def call(self, service: str, call: str, args: list | None = None):
        self._uuid = str(uuid.uuid4())
        data = {
            "service": service,
            "call": call,
            "uuid": self._uuid,
            "args": [] if args is None else args,
        }
        return self._call(data)

    def _call(self, data):
        try:
            jsondata = json.dumps(data, cls=Object_To_JSON_Encoder, ensure_ascii=True)
            if self._debug:
                self._logger.debug(f"jsondata: {jsondata}")
            self._connection._request_cache.push(self)
            return self._connection.send(jsondata)
        except Exception as e:
            self._logger.warning(f"Failed to make WS call: {str(e)}")
            self._error = e
            self._connection._request_cache.failed(self)
            return None

    def data(self, data):
        with self._data_condition:
            result = True
            if self._error is not None:
                result = False
            elif self._reply is None:
                self._reply = data
            else:
                result = False
            self._logger.debug("Request got data, notify")
            self._data_condition.notify_all()
            return result

    def wait(self, timeout: int | None = None):
        with self._data_condition:
            if self._reply is None and self._error is None:
                if timeout is None:
                    timeout = self._timeout
                self._logger.debug(f"Request wait for: {timeout}")
                self._data_condition.wait(timeout)
            if not self.error():
                self._logger.debug(f"Request complete, no error, data: {self._reply is not None}")
                return self._reply
        return None

    def error(self):
        if self._error is not None:
            return self._error
        elif self._reply is None:
            return False
        elif not isinstance(self._reply, dict):
            return False
        elif "errormessage" in self._reply:
            return self._reply["errormessage"]
        return False
