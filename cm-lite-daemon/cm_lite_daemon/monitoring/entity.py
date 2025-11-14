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

from uuid import UUID

from cm_lite_daemon.base import Base


class Entity(Base):
    def __init__(self, data=None):
        self.uuid = UUID(int=0)
        self.name = ""
        self.types = []
        self.resources = []
        self.disabled = False
        self.environment = None
        if data is not None:
            super().__init__(data)
            self.normalize()

    def normalize(self):
        if isinstance(self.uuid, str):
            self.uuid = UUID(self.uuid)
        self.name = self.name.lower()
        self.types = [it.lower() for it in self.types]
        self.resources = [it.lower() for it in self.resources]

    def match(self, name, type=None):
        if self.name.lower() == name.lower():
            if type is None:
                return True
            return type.lower() in self.types
        return False

    def type_index(self, types):
        result = len(types) + 1
        if result > 1:
            types = [it.lower() for it in types]
            result = min([self.types.index(x) if x in self.types else result for x in types])
        return result
