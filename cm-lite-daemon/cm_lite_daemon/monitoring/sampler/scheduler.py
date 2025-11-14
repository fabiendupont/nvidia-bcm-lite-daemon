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


from multiprocessing.pool import ApplyResult
from multiprocessing.pool import ThreadPool


class Scheduler:
    def __init__(self, threads=8):
        if threads is None:
            self.pool = None
        else:
            self.pool = ThreadPool(threads)
        self._tasks = []

    def wait(self):
        if self.pool is not None:
            self.pool.close()
            self.pool.join()
            return True
        return False

    def update(self, _tasks):
        self._tasks = _tasks

    def run_once(self, now, asynchronous=True):
        todo = [it for it in self._tasks if it.run(now, 0)]
        started = [it.start(now, None, self.pool, asynchronous) for it in todo]
        count = sum([1 for it in started if isinstance(it[0], ApplyResult) or it[0]])
        return (count, len(todo))
