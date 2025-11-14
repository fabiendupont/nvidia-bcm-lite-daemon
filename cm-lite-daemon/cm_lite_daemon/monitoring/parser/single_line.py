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

import shlex

from cm_lite_daemon.monitoring.parser.parser import Parser
from cm_lite_daemon.monitoring.parser.value import Value
from cm_lite_daemon.monitoring.parser.value_interpreter import Value_Interpreter


class Single_Line(Parser):
    def __init__(self, producer, entity, name, parameter, enum_value_cache):
        super().__init__(producer, entity, enum_value_cache)
        self.name = name
        self.parameter = parameter
        self.value_interpreter = Value_Interpreter(enum_value_cache)

    def parse(self, data, now=0, info=None):
        values = []
        now = self._timestamp_in_milliseconds(now)
        words = shlex.split(data)
        value = {
            "producer": self.producer,
            "timestamp": now,
            "entity": self.entity,
            "measurable": self.name,
            "parameter": self.parameter,
        }
        if len(words) > 1:
            value["info"] = words[1]
        elif bool(info):
            value["info"] = info
        (value["rate"], value["raw"]) = self.value_interpreter.parse_value(self.name, self.parameter, words[0])
        values.append(Value(value))
        return values
