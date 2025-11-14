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

import yaml

from cm_lite_daemon.monitoring.parser.parser import Parser


class Parser_YAML(Parser):
    def __init__(self, producer, entity, enum_value_cache):
        super().__init__(producer, entity, enum_value_cache)

    def _parse(self, data):
        parsed = None
        try:
            parsed = yaml.safe_load(data)
        except Exception:
            return None
        if not isinstance(parsed, list):
            return None
        return parsed

    def _get(self, data, field, default=None):
        if not isinstance(field, list):
            field = [field]
        for it in field:
            if it in data:
                return data[it]
        return default
