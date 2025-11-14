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


class Initialize_text(Parser_text):
    def __init__(self, producer, entity, enum_value_cache):
        super().__init__(producer, entity, enum_value_cache)

    def _parse_enum_range(self, text):
        enum = []
        index = 0
        for it in text.split(","):
            it = it.strip()
            if len(it) == 0:
                continue
            idx = it.find(":")
            if idx < 0:
                enum.append(it)
            else:
                try:
                    start = idx + 1
                    index = float(it[start:])
                    enum.append((it[0:idx], index))
                except Exception:
                    pass
            index += 1
        return enum

    def parse(self, data):
        current_entity = self.entity
        current_length = 0
        current_consolidators = ""
        definitions = []
        for line in data.split("\n"):
            if (len(line) == 0) or (line[0] == "#"):
                continue
            words = shlex.split(line)
            first_word = words[0].lower()
            if first_word in ["measurable", "metric", "healthcheck", "check"]:
                definition = {"producer": self.producer, "entity": current_entity}
                if len(words) < 3:
                    continue
                (
                    definition["measurable"],
                    definition["parameter"],
                ) = self.measurable_paramater(words[1])
                if len(definition["measurable"]) == 0:
                    continue
                if current_length:
                    definition["length"] = current_length
                arg_counter = 2
                if first_word == "metric":
                    definition["consolidators"] = current_consolidators
                    definition["unit"] = words[arg_counter]
                    arg_counter += 1
                if arg_counter < len(words):
                    definition["type"] = words[arg_counter]
                    arg_counter += 1
                if arg_counter < len(words):
                    definition["description"] = words[arg_counter]
                    arg_counter += 1
                if first_word in ["healthcheck", "check"]:
                    definition["range"] = {"type": "HealthCheck"}
                else:
                    if arg_counter < len(words):
                        if words[arg_counter].lower() != "enum":
                            definition["cumulative"] = words[arg_counter].lower() == "yes"
                            arg_counter += 1
                    if arg_counter + 1 < len(words):
                        if words[arg_counter].lower() == "enum":
                            values = self.enum_value_cache.set(
                                definition["measurable"],
                                definition["parameter"],
                                self._parse_enum_range(words[arg_counter + 1]),
                            )
                            definition["range"] = {"type": "Enum", "values": values}
                            if "consolidators" in definition:
                                del definition["consolidators"]
                            if "unit" in definition:
                                del definition["unit"]
                        else:
                            try:
                                minimum = float(words[arg_counter])
                                maximum = float(words[arg_counter + 1])
                                if minimum or maximum:
                                    definition["range"] = {
                                        "type": "Metric",
                                        "min": minimum,
                                        "max": maximum,
                                    }
                            except Exception:
                                pass
                definitions.append(definition)
            elif first_word == "entity":
                if (len(words) == 1) or (words[1] == "-"):
                    current_entity = self.entity
                else:
                    current_entity = words[1]
            elif first_word == "rawlength":
                try:
                    current_length = int(words[1])
                except Exception:
                    current_length = 0
            elif first_word == "consolidators":
                if len(words) > 1:
                    current_consolidators = words[1]
                else:
                    current_consolidators = ""
            else:
                # TODO: error
                pass
        return definitions
