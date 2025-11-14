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


import math


class Task:
    def __init__(self, interval: int, offset: int = 0):
        self.interval = interval
        self.offset = offset

    def next(self, now):
        if self.interval == 0:
            return 0
        return now + self.interval - ((now - self.offset) % self.interval)

    def run(self, now, last=None):
        _run = self.interval and (((now - self.offset) % self.interval) == 0)
        if last is None or _run:
            return _run
        elif (self.interval == 0) or (last == 0):
            return False
        w0 = math.floor((now - self.offset) / self.interval)
        w1 = math.floor((last - self.offset) / self.interval)
        if w0 == w1:
            return False
        dd = (now - self.offset) % self.interval
        return (2 * dd) < self.interval

    def wait(self, now, last):
        if self.interval == 0:
            return -1
        if self.run(now):
            if now == last:
                return self.interval
            return 0
        w0 = math.floor((now - self.offset) / self.interval)
        w1 = math.floor((last - self.offset) / self.interval)
        if w0 == w1:
            return self.next(now) - now
        dd = (now - self.offset) % self.interval
        if (2 * dd) < self.interval:
            return 0
        return self.next(now) - now
