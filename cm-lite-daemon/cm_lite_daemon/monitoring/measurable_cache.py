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

from cm_lite_daemon.monitoring.measurable import Measurable


class Measurable_Cache:
    def __init__(self, measurables=None):
        self._measurables = [] if measurables is None else measurables
        self._condition = threading.Condition()

    def size(self):
        self._condition.acquire()
        n = len(self._measurables)
        self._condition.release()
        return n

    def update(self, measurables):
        self._condition.acquire()
        self._measurables = measurables
        self._condition.release()

    def find(self, name, parameter=""):
        self._condition.acquire()
        matches = [it for it in self._measurables if it.match(name, parameter)]
        self._condition.release()
        if len(matches) == 0:
            return None
        return matches[0]

    def changed(self, added, updated, removed):
        self._condition.acquire()
        measurables = [Measurable(it) for it in added] + [Measurable(it) for it in updated]
        old = {it.uuid: it for it in self._measurables if it.uuid not in removed}
        old.update({it.uuid: it for it in measurables})
        self._measurables = old.values()
        n = len(self._measurables)
        self._condition.release()
        return n

    def producers(self, measurables):
        measurables = set(measurables)
        self._condition.acquire()
        uuids = [it.producer for it in self._measurables if it.uuid in measurables]
        self._condition.release()
        return list(set(uuids))
