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

from cm_lite_daemon.monitoring.parser.value import Value
from cm_lite_daemon.monitoring.parser.value_interpreter import Value_Interpreter


class Sample_Generic(Value_Interpreter):
    def parse(self, data, now=0, info=None):
        parsed = self._parse(data)
        if parsed is None:
            return parsed
        now = self._timestamp_in_milliseconds(now)
        values = []
        for it in parsed:
            value = {"producer": self.producer}
            value["measurable"] = self._get(it, ["measurable", "metric", "healthcheck", "check"])
            if value["measurable"] is None:
                continue
            value["timestamp"] = self._get(it, "timestamp", now)
            value["entity"] = self._get(it, "entity", self.entity)
            value["parameter"] = self._get(it, "parameter", "")
            value["info"] = self._get(it, "info", "" if info is None else info)
            if value["info"] is None:
                value["info"] = ""
            value["severity"] = self._get(it, "severity", 0)
            (value["rate"], value["raw"]) = self.parse_value(
                value["measurable"], value["parameter"], self._get(it, "value", 0)
            )
            values.append(Value(value))
        return values
