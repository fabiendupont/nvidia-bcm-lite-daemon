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

from subprocess import PIPE
from subprocess import Popen


class Script:
    def __init__(self, logger):
        self._logger = logger
        self._reset()

    def _reset(self) -> None:
        self.exit_code = None
        self.stdout = None
        self.stderr = None

    def run(
        self, args: list[str], timeout: int | None = 15, log_stdout: bool = True, env: dict[str, str] | None = None
    ) -> tuple[bool, str | None]:
        self._logger.debug(f"Run: {args}")
        try:
            proc = Popen(
                args,
                env=env,
                stdout=PIPE,
                stderr=PIPE,
                shell=False,
                close_fds=True,
            )
            self.exit_code = proc.wait(timeout=timeout)
            self.stdout = proc.stdout.read().decode("utf-8")
            self.stderr = proc.stderr.read().decode("utf-8")
            if bool(self.stdout) and log_stdout:
                self._logger.info(self.stdout)
            if bool(self.stderr):
                self._logger.warning(self.stderr)
            self._logger.debug(f"Ran: {args}, exit code: {self.exit_code}")
            return self.exit_code == 0, self.stdout
        except FileNotFoundError:
            self._logger.info(f"Unable to run: {args[0]}: file not found")
        except Exception:
            self._logger.info(f"Timeout, after: {timeout}")
            proc.kill()
        return False, None
