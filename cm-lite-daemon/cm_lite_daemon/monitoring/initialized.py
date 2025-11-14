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


class Initialized:
    MAX = 1

    def __init__(self, timestamp=0):
        self.timestamp = timestamp
        self.count = 0

    def check(self, now):
        if now < self.timestamp:
            return False
        old = self.count
        self.count = (self.count + 1) % self.MAX
        return (self.count & old) == 0

    def done(self, now):
        self.timestamp = now
        self.count = 0

    def clear(self):
        if self.timestamp == 0:
            return 0
        self.timestamp = 0
        self.count = (self.count + 1) % self.MAX
        self.count += 1
        return self.count
