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


class Last_Raw_Data_Cache:
    def __init__(self, time_unit=1000.0):
        self._last = dict()
        self._time_unit = time_unit

    def clear(self):
        self._last.clear()

    def size(self):
        return len(self._last)

    def update(self, measurables):
        cumulative_measurables_uuids = [it.uuid for it in measurables if it.cumulative]
        keep = {k: v for k, v in list(self._last.items()) if k[1] in cumulative_measurables_uuids}
        self._last = {(0, k): (-1, -1) for k in cumulative_measurables_uuids}
        self._last.update(keep)

    def calculate_rate(self, entity, measurable, time, raw, update=True):
        if (entity, measurable) in self._last:
            old_time, old_raw = self._last[(entity, measurable)]
        elif (0, measurable) in self._last:
            old_time, old_raw = 0, 0
        else:
            return None

        if (time <= old_time) or (old_time == 0):
            rate = None
        elif raw < old_raw:
            rate = 0
        else:
            rate = self._time_unit * float(raw - old_raw) / (time - old_time)
        if update:
            self._last[(entity, measurable)] = (time, raw)
        return rate
