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


class Cache:
    def __init__(self, logger, max_size=1024 * 1024):
        self._logger = logger
        self._data = []
        self._last = []
        self._max_size = max_size
        self._condition = threading.Condition()

    def clear(self):
        self._condition.acquire()
        self._data = []
        self._last = []
        self._condition.release()

    def push(self, data):
        self._condition.acquire()
        if isinstance(data, list):
            self._data += data
        else:
            self._data.append(data)
        n = len(self._data)
        if n > self._max_size:
            count = n - self._max_size
            self._logger.info(f"Cache has too much data, deleting: {int(count)}")
            del self._data[0:count]
        self._condition.release()
        return n

    def fetch(self, last_good=True):
        self._condition.acquire()
        if last_good:
            self._last = self._data
        else:
            self._last += self._data
            if len(self._last) > self._max_size:
                count = len(self._last) - self._max_size
                del self._last[0:count]
        data = self._last
        self._data = []
        self._logger.debug(f"Cache fetch, size: {len(data)}, last good {int(last_good)}")
        self._condition.release()
        return data
