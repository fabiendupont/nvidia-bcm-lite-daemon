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

import os

from cm_lite_daemon.script import Script


class Service:
    max_failures = 10
    fail_commands = {"start", "restart", "reload"}
    event_operation = {
        "start": "started",
        "stop": "stopped",
        "restart": "restarted",
        "reload": "reloaded",
    }
    alternatives = {
        "ntp": ["ntpsec"],
    }

    def __init__(self, cmdaemon, logger, data: dict):
        self._cmdaemon = cmdaemon
        self._logger = logger
        self.data = data
        self.first_check = True
        self.fail_count = 0

    @property
    def valid(self) -> bool:
        if "name" in self.data:
            self._logger.debug(f"Service valid: {self.name}")
            return True
        self._logger.info("Service without a name")
        return False

    @property
    def name(self) -> str:
        name = self.data.get("name")
        alternatives = self.alternatives.get(name, None)
        if bool(alternatives):
            for it in [name] + alternatives:
                if os.path.exists(f"/lib/systemd/system/{it}.service"):
                    return it
        return name

    @property
    def failing(self) -> bool:
        if not self.data.get("monitored", False):
            return False
        return self.fail_count > self.max_failures

    def call(self, command: str, args: list[str] = None, event: bool = True) -> bool:
        final_args = ["/usr/bin/systemctl", command, self.name]
        if args is not None:
            final_args += args
        script = Script(self._logger)
        success, stdout = script.run(final_args, log_stdout=False)
        if success:
            if command in self.fail_commands:
                self.fail_count = 0
            self._logger.debug(f"Service {' '.join(final_args)}")
        else:
            if command in self.fail_commands:
                self.fail_count += 1
            self._logger.info(f"Service {' '.join(final_args)} failed, count: {self.fail_count}, event: {event}")
        if event and not self.failing:
            self._cmdaemon.send_service_event(self.name, self.event_operation.get(command, command), success)
        return success

    def status(self, args: list[str] = None, event: bool = False) -> bool:
        return self.call("status", args, event)

    def start(self, args: list[str] = None, event: bool = True) -> bool:
        return self.call("start", args, event)

    def restart(self, args: list[str] = None, event: bool = True) -> bool:
        return self.call("restart", args, event)

    def reload(self, args: list[str] = None, event: bool = True) -> bool:
        return self.call("reload", args, event)

    def stop(self, args: list[str] = None, event: bool = True) -> bool:
        return self.call("stop", args, event)

    def reset(self, args: list[str] = None, event: bool = True) -> bool:
        self.fail_count = 0
        return True

    def check(self, args: list[str] = None, event: bool = True) -> bool:
        if not self.status(args):
            if (self.first_check and self.data.get("autostart", False)) or self.data.get("monitored", False):
                self._logger.debug(f"Service check failed {self.name} starting")
                first, self.first_check = self.first_check, False
                return self.start(args, event and not first)
        return True

    def info(self) -> dict:
        if self.failing:
            status = "FAILING"
        elif self.status():
            status = "UP"
        else:
            status = "DOWN"
        return {
            "baseType": "OSService",
            "ref_node_uuid": self._cmdaemon.uuid,
            "ref_osservice_config_uuid": self.data.get("UUID", ""),
            "name": self.data.get("name"),
            "status": status,
        }
