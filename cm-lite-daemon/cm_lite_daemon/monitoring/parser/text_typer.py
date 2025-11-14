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


class Text_Typer:
    TEXT = 1
    JSON = 2
    YAML = 3
    METRIC = 4
    CHECK = 5

    def determine_format(self, lines, default=None):
        if (default is not None) and (default in [self.TEXT, self.JSON, self.YAML, self.METRIC, self.CHECK]):
            return default
        elif len(lines) == 0:
            return None

        i = 0
        first = None
        while i < len(lines):
            j = lines.find("\n", i)
            if j < 0:
                j = len(lines)
            first = lines[i:j].strip()
            if len(first):
                break
            i = j + 1
        if first is None:
            return None

        first = first.lower()
        if (first[0] == "[") or (first[0] == "{") or ((first[0] == "#") and ("json" in first)):
            return self.JSON

        if (first == "---") or ((first[0] == "#") and ("yaml" in first)):
            return self.YAML
        return self.TEXT
