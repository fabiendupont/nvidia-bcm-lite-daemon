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

from cm_lite_daemon.monitoring.parser.parser_yaml import Parser_YAML
from cm_lite_daemon.monitoring.parser.sample_generic import Sample_Generic


class Sample_YAML(Parser_YAML, Sample_Generic):
    def __init__(self, producer, entity, enum_value_cache):
        super().__init__(producer, entity, enum_value_cache)
