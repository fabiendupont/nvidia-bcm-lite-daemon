#
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


class Measurable(Base):
    def __init__(self, data=None):
        self.uuid = UUID(int=0)
        self.producer = UUID(int=0)
        self.disabled = False
        self.name = ""
        self.parameter = ""
        self.kind = ""
        if data is not None:
            super().__init__(data)
            self.normalize()

    def normalize(self):
        if isinstance(self.uuid, str):
            self.uuid = UUID(self.uuid)
        if isinstance(self.producer, str):
            self.producer = UUID(self.producer)
        self.name = self.name.lower()
        self.parameter = self.parameter.lower()
        self.kind = self.kind.lower()

    def match(self, name, parameter=""):
        return (name.lower() == self.name) and (parameter.lower() == self.parameter)

    def is_metric(self):
        return self.kind == "metric"

    def is_check(self):
        return self.kind == "check"

    def is_enum(self):
        return self.kind == "enum"
