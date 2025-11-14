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


class Initialize_Generic:
    def parse(self, data):
        parsed = self._parse(data)
        if parsed is None:
            return parsed
        definitions = []
        for it in parsed:
            name = self._get(it, ["measurable", "metric", "healthcheck", "check"])
            if name is None:
                continue
            definition = {
                "producer": self.producer,
                "measurable": name,
                "entity": self._get(it, "entity", self.entity),
                "parameter": self._get(it, "parameter", ""),
                "unit": self._get(it, "unit", ""),
                "type": self._get(it, "class", "Undefined"),
                "description": self._get(it, "description", ""),
                "consolidators": self._get(it, "consolidators", ""),
                "length": self._get(it, "length", 0),
                "age": self._get(it, "age", 0),
                "cumulative": it.get("cumulative", False) in (1, True, "yes"),
            }
            if "check" in it or "healthcheck" in it:
                definition["range"] = {"type": "HealthCheck"}
            elif "enum" in it:
                values = self.enum_value_cache.set(definition["measurable"], definition["parameter"], it["enum"])
                definition["range"] = {"type": "Enum", "values": values}
            else:
                minimum = self._get(it, "min", 0)
                maximum = self._get(it, "max", 0)
                if minimum or maximum:
                    definition["range"] = {
                        "type": "Metric",
                        "min": minimum,
                        "max": maximum,
                    }
            definitions.append(definition)
        return definitions
