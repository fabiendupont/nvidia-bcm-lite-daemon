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

import json

from cm_lite_daemon.object_to_json_encoder import Object_To_JSON_Encoder


class Base:
    def __init__(self, data=None):
        if isinstance(data, dict):
            self.__dict__.update(data)

    def __repr__(self, indent=4):
        return json.dumps(self.__dict__, cls=Object_To_JSON_Encoder, indent=indent, ensure_ascii=True)

    def __cmp__(self, other):
        if list(self.__dict__.keys()) != list(other.__dict__.keys()):
            if list(self.__dict__.keys()) < list(other.__dict__.keys()):
                return -1
            else:
                return 1
        for key, value in self.__dict__.items():
            if value != other.__dict__[key]:
                if value < other.__dict__[key]:
                    return -1
                else:
                    return 1
        return 0

    def __eq__(self, other):
        return self.__cmp__(other) == 0

    def __lt__(self, other):
        return self.__cmp__(other) < 0

    def __gt__(self, other):
        return self.__cmp__(other) > 0
