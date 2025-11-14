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


class Enum_Value_Cache:
    def __init__(self):
        self.enums = dict()

    def clear(self):
        self.enums = dict()

    def elements(self):
        return sum(len(self.enums[key]) for key in self.enums)

    def set(self, measurable, parameter="", keys=None):
        values = []
        if keys is None:
            del self.enums[(measurable, parameter)]
        else:
            work = dict()
            n = 0
            if isinstance(keys, list):
                for it in keys:
                    work[str(it).lower()] = n
                    n += 1
            elif isinstance(keys, dict):
                for k, v in keys.items():
                    work[str(k).lower()] = v
            self.enums[(measurable, parameter)] = work
            values = sorted(
                [{"key": index, "value": value} for value, index in work.items()],
                key=lambda item: item["key"],
            )
        return values

    def get(self, measurable, parameter, text):
        if (measurable, parameter) not in self.enums:
            return None
        work = self.enums[(measurable, parameter)]
        text = text.lower()
        if text in work:
            return work[text]
        return None
