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


class Execution_Multiplexer(Base):
    def __init__(self, data=None):
        self.uuid = UUID(int=0)
        self.name = ""
        if data is not None:
            super().__init__(data)
            self.normalize()

    def normalize(self):
        self.name = self.name.lower()
