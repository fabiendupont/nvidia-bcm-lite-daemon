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


class Source_State_Cache:
    UP = 0
    DOWN = 1
    CLOSED = 2

    def __init__(self):
        self._states = dict()

    def size(self):
        return len(self._states)

    def clear(self):
        self._states.clear()

    def add(self, key, state=UP):
        self._states[key] = state

    def remove(self, keys):
        self._states = {k: v for k, v in list(self._states.items()) if k not in keys}

    def get(self, key, missing_state=UP):
        if key in self._states:
            return self._states[key]
        return missing_state
