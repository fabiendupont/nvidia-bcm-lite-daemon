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


class Value_Interpreter:
    PASS_VALUE = 0
    FAIL_VALUE = 2
    UNKNOWN_VALUE = 1

    def __init__(self, enum_value_cache):
        self.enum_value_cache = enum_value_cache

    def parse_value(self, measurable, parameter, text):
        if isinstance(text, (int, float)):
            return (text, text)
        text = text.lower()
        if text == "pass":
            return (self.PASS_VALUE, self.PASS_VALUE)
        elif text == "fail":
            return (self.FAIL_VALUE, self.FAIL_VALUE)
        elif text == "unknown":
            return (self.UNKNOWN_VALUE, self.UNKNOWN_VALUE)
        elif text == "nodata":
            return (None, None)
        try:
            value = float(text)
            return (value, int(value))
        except Exception:
            enum = self.enum_value_cache.get(measurable, parameter, text)
            return (enum, enum)
