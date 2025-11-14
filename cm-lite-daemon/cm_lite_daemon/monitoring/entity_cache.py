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

from cm_lite_daemon.monitoring.entity import Entity


class Entity_Cache:
    def __init__(self, entities=None, type_order=None):
        self._entities = [] if entities is None else entities
        self._type_order = ["Device"] if type_order is None else type_order
        self._condition = threading.Condition()

    def size(self):
        self._condition.acquire()
        n = len(self._entities)
        self._condition.release()
        return n

    def update(self, entities):
        self._condition.acquire()
        self._entities = entities
        self._condition.release()

    def get(self, uuid):
        self._condition.acquire()
        matches = [it for it in self._entities if it.uuid == uuid]
        self._condition.release()
        if len(matches) == 0:
            return None
        return matches[0]

    def find(self, name, type=None):
        self._condition.acquire()
        matches = [it for it in self._entities if it.match(name, type)]
        self._condition.release()
        if len(matches) == 0:
            return None
        elif len(matches) == 1:
            return matches[0]
        return min((it.type_index(self._type_order), it.uuid, it) for it in matches)[2]

    def changed(self, added, updated, removed):
        self._condition.acquire()
        entities = [Entity(it) for it in added] + [Entity(it) for it in updated]
        old = {it.uuid: it for it in self._entities if it.uuid not in removed}
        old.update({it.uuid: it for it in entities})
        self._entities = old.values()
        n = len(self._entities)
        self._condition.release()
        return n
