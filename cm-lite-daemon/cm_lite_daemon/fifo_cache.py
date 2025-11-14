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

import threading
import time


class FIFOCache:
    def __init__(self, max_elements: int = 65536):
        self.max_elements = max_elements
        self.elements = []
        self._condition = threading.Condition()

    def add(self, element) -> int:
        with self._condition:
            if len(self.elements) >= self.max_elements:
                self.elements = self.elements[1:]
            self.elements.append((time.time(), element))
            return len(self.elements)

    def get(self, timed: bool = False, delete: bool = True) -> list:
        with self._condition:
            if timed:
                result = self.elements
            else:
                result = [value for _, value in self.elements]
            if delete:
                self.elements = []
            return result
