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

from cm_lite_daemon.monitoring.parser.parser_text import Parser_text
from cm_lite_daemon.monitoring.parser.value import Value
from cm_lite_daemon.monitoring.parser.value_interpreter import Value_Interpreter


class Sample_text(Parser_text, Value_Interpreter):
    def __init__(self, producer, entity, enum_value_cache):
        super().__init__(producer, entity, enum_value_cache)
        self.value_interpreter = Value_Interpreter(enum_value_cache)

    def parse(self, data, now=0, info=None):
        values = []
        current_entity = self.entity
        now = self._timestamp_in_milliseconds(now)
        for line in data.split("\n"):
            if (len(line) == 0) or (line[0] == "#"):
                continue
            words = shlex.split(line)
            first_word = words[0].lower()
            if first_word in ["measurable", "metric", "healthcheck", "check"]:
                if len(words) < 3:
                    continue
                value = {
                    "producer": self.producer,
                    "timestamp": now,
                    "entity": current_entity,
                }
                value["measurable"], value["parameter"] = self.measurable_paramater(words[1])
                if len(value["measurable"]) == 0:
                    continue
                if len(words) > 3:
                    value["info"] = words[3]
                elif bool(info):
                    value["info"] = info
                if len(words) > 4:
                    try:
                        value["severity"] = int(words[4])
                    except Exception:
                        pass
                (value["rate"], value["raw"]) = self.value_interpreter.parse_value(
                    value["measurable"], value["parameter"], words[2]
                )
                values.append(Value(value))
            elif first_word == "entity":
                if (len(words) <= 1) or (words[1] == "-"):
                    current_entity = self.entity
                else:
                    current_entity = words[1]
        return values
