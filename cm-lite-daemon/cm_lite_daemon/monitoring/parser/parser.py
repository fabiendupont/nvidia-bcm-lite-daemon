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


class Parser:
    def __init__(self, producer, entity, enum_value_cache):
        self.producer = producer
        self.entity = entity
        self.enum_value_cache = enum_value_cache

    def _timestamp_in_milliseconds(self, timestamp):
        if isinstance(timestamp, float):
            return int(timestamp * 1000)
        return timestamp
