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

from cm_lite_daemon.monitoring.parser.parser import Parser


class Parser_text(Parser):
    def __init__(self, producer, entity, enum_value_cache):
        super().__init__(producer, entity, enum_value_cache)

    def measurable_paramater(self, name):
        idx = name.find(":")
        if idx < 0:
            return (name.strip(), "")
        start = idx + 1
        return (name[0:idx].strip(), name[start:])
