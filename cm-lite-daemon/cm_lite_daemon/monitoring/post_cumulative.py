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


class PostCumulative:
    def __init__(self, measurable_cache):
        self._measurable_cache = measurable_cache
        self.data = []

    def process(self, entity, measurable, now, rate):
        if measurable.name.lower() == "cpuidle":
            cpu_usage_measurable = self._measurable_cache.find("CPUUsage", measurable.parameter)
            if cpu_usage_measurable is not None:
                value = None if rate is None else (100 - rate) / 100.0
                self.data.append(
                    {
                        "entity": entity.uuid,
                        "measurable": cpu_usage_measurable.uuid,
                        "timestamp": now,
                        "value": value,
                        "raw": value,
                        "info": "",
                        "severity": 0,
                    }
                )

    def get(self):
        data, self.data = self.data, []
        return data
