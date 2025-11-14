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

from cm_lite_daemon.monitoring.source_state_cache import Source_State_Cache


class Task_Run_Checker:
    def __init__(self, source_state_cache):
        self._source_state_cache = source_state_cache

    def check(self, source, for_self, run_if_other_down):
        state = self._source_state_cache.get(source)
        if state == Source_State_Cache.CLOSED:
            return False
        elif state == Source_State_Cache.UP:
            return True
        else:
            return for_self or run_if_other_down
