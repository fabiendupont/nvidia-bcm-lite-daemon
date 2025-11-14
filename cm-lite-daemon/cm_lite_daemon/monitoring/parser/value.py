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

from __future__ import annotations

from uuid import UUID

from cm_lite_daemon.base import Base


class Value(Base):
    def __init__(
        self,
        producer: UUID | None = None,
        timestamp: int = 0,
        raw: float = 0,
        rate: float = 0,
        severity: int = 0,
        nodata: bool = False,
        entity: str | UUID | None = None,
        measurable: str | UUID | None = None,
        parameter: str | None = None,
        info: str = "",
    ):
        if producer is None:
            self.producer = UUID(int=0)
        else:
            self.producer = producer
        self.timestamp = timestamp
        self.entity = entity
        self.measurable = measurable
        self.parameter = parameter
        self.raw = raw
        self.rate = rate
        self.severity = severity
        self.nodata = nodata
        self.info = info
        super().__init__(producer)

    def get_name_uuid(self) -> UUID:
        if (
            (self.entity is not None)
            and isinstance(self.entity, str)
            and (len(self.entity) == 37)
            and (self.entity[0] == "#")
        ):
            return UUID(self.entity[1:])
        return UUID(int=0)

    def get_name_type(self):
        if (self.entity is not None) and isinstance(self.entity, str):
            idx = self.entity.find(":")
            if idx >= 0:
                start = idx + 1
                return (self.entity[start:], self.entity[0:idx])
            else:
                return (self.entity, "")
        return None
