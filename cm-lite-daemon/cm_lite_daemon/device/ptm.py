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

from __future__ import annotations

import json
import os

from cm_lite_daemon.script import Script


class PTM:
    def __init__(self, cmdaemon, logger, protocols: list[str] | None = None, timeout: int = 15):
        self._cmdaemon = cmdaemon
        self._logger = logger
        self.timeout = timeout
        self.ptmctl = "ptmctl"
        for path in ("/usr/sbin", "/usr/bin", "/sbin", "/bin"):
            self.ptmctl = f"{path}/ptmctl"
            if os.path.exists(self.ptmctl):
                break

    @property
    def info(self) -> list[dict[str, str | float]] | None:
        try:
            if bool(self._cmdaemon.fake.ptm) and os.path.exists(self._cmdaemon.fake.ptm):
                self._logger.info(f"Gather PTM info from: {self._cmdaemon.fake.ptm}")
                with open(self._cmdaemon.fake.ptm) as fd:
                    data = json.load(fd)
            else:
                success, data = Script(self._logger).run(
                    [self.ptmctl, "-d", "-j"],
                    self.timeout,
                    False,
                    env=self._cmdaemon.venv_free_environment,
                )
                if success:
                    self._logger.debug(f"PTM, summary length: {len(data)}")
                    data = json.loads(data)
                else:
                    return None

            all_info = [port for _, port in self.data.items()]
            self._logger.info(f"PTM info, defined {len(all_info)}, data: {len(data)}")
            return all_info
        except Exception as e:
            self._logger.info(f"PTM info failed: {e}")
            return None
