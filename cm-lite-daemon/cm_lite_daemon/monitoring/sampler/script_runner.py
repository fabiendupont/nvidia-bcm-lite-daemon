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

import os
from subprocess import PIPE
from subprocess import Popen
from subprocess import TimeoutExpired


class Script_Runner:
    def __init__(
        self,
        cmdaemon,
        command,
        arguments=None,
        env=None,
        pool=None,
        shell=False,
        timeout=15,
        follow_up=None,
        follow_up_args=None,
    ):
        self._cmdaemon = cmdaemon
        self.command = command
        self.arguments = [] if arguments is None else arguments
        self.__command_line = [self.command] + self.arguments
        self.env = self._cmdaemon.venv_free_environment if bool(self._cmdaemon) else None
        if not bool(self.env):
            self.env = os.environ
        if env is not None:
            self.env.update(env)
        self._fdr, self._fdw = os.pipe()
        self.env["CMD_INFO_FD"] = str(self._fdw)
        self.timeout = timeout
        self.follow_up = follow_up
        self.follow_up_args = [] if follow_up_args is None else follow_up_args
        self.pool = pool
        self.shell = shell
        self.output = None
        self.error = None
        self.info = None
        self.exit_code = None
        self.killed = False
        self.done = None
        self.__proc = None
        self.__timer = None

    def _kill(self):
        try:
            self.proc.kill()
            self.killed = True
        except Exception:
            pass

    def _launch(self):
        try:
            with open(os.devnull, "r") as tmp_null:
                if bool(self._cmdaemon):
                    self._cmdaemon._logger.debug(f"execute {self.__command_line}")
                self.proc = Popen(
                    self.__command_line,
                    env=self.env,
                    stdout=PIPE,
                    stderr=PIPE,
                    stdin=tmp_null,
                    shell=self.shell,
                    pass_fds=(self._fdr, self._fdw),
                    close_fds=True,
                    text=True,
                )
                try:
                    self.output, self.error = self.proc.communicate(timeout=self.timeout)
                    self.exit_code = self.proc.returncode
                    if bool(self._cmdaemon):
                        self._cmdaemon._logger.debug(f"done {self.__command_line}, exit: {self.exit_code}")
                except TimeoutExpired:
                    if bool(self._cmdaemon):
                        self._cmdaemon._logger.info(f"kill {self.__command_line}")
                    self.killed = True
                    self.proc.kill()
                    self.output, self.error = self.proc.communicate()
                os.close(self._fdw)
                self._fdw = None
                with open(self._fdr) as fd:
                    self.info = fd.read()
                self.done = True
        except Exception as e:
            if bool(self._fdw):
                os.close(self._fdw)
            os.close(self._fdr)
            self.error = e
            self.done = False
        if self.follow_up is not None:
            self.follow_up(self, *self.follow_up_args)
        return self.done

    def run(self, asynchronous=True):
        if not asynchronous:
            return self._launch()
        elif self.pool is None:
            return False
        return self.pool.apply_async(self._launch)
