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

import typing

from cm_lite_daemon.monitoring.sampler.sampler_task import Sampler_Task

if typing.TYPE_CHECKING:
    from uuid import UUID


class Internal_Sampler_Task(Sampler_Task):
    def __init__(self, interval: int, offset: int = 0, producer: UUID | None = None):
        super().__init__(interval, offset, producer)

    def _timestamp_in_milliseconds(self, timestamp):
        if isinstance(timestamp, float):
            return int(timestamp * 1000)
        return timestamp
