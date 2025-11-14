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

from cm_lite_daemon.script import Script


class Device:
    def __init__(self, cmdaemon, logger):
        self._cmdaemon = cmdaemon
        self._logger = logger

    def stop(self) -> None:
        pass

    def do_maintenance(self) -> None:
        pass

    def reboot(self) -> None:
        return None

    def shutdown(self) -> None:
        return None

    def get_port_by_mac(self, mac: str) -> tuple[int | None, int | None]:
        return None, None

    def sync_log(self, path: bool = False) -> str:
        return "Not implemented for this type of device"

    def commands(self, force: bool = False) -> dict | None:
        return None

    def diff_commands(self) -> tuple[int, dict | None, str]:
        return -1, None, "Not implemented for this type of device"

    def show_commands(self) -> tuple[int, dict | None, str]:
        return -1, None, "Not implemented for this type of device"

    def save_commands(self) -> tuple[int, str, str]:
        return -1, "", "Not implemented for this type of device"

    def detach_commands(self) -> tuple[int, str, str]:
        return -1, "", "Not implemented for this type of device"

    def apply_commands(self, staged: bool = False, stage_only: bool = False) -> tuple[int, str, str]:
        return -1, "", "Not implemented for this type of device"

    def show_ptm_topology(self) -> tuple[int, str, str]:
        return -1, "", "Not implemented for this type of device"

    def apply_ptm_topology(self, data: str | None) -> tuple[int, str, str]:
        return -1, "", "Not implemented for this type of device"

    def sys_info(self) -> dict | None:
        return None

    def factory_reset(self, force: bool) -> dict[str, str | bool]:
        return {"success": False, "message": "Not implemented for this type of device"}

    def show_system_ztp(self) -> dict[str, str | bool]:
        return {"success": False, "message": "Not implemented for this type of device"}

    def show_sdn_partition(self) -> dict[str, str | bool]:
        return {"success": False, "message": "Not implemented for this type of device"}

    def nvfabric_start(self) -> dict[str, str | bool]:
        return {"success": False, "message": "Not implemented for this type of device"}

    def nvfabric_stop(self) -> dict[str, str | bool]:
        return {"success": False, "message": "Not implemented for this type of device"}

    def nvfabric_status(self) -> dict[str, str | bool]:
        return {"success": False, "message": "Not implemented for this type of device"}

    def nvfabric_health(self) -> dict[str, str | bool]:
        return {"success": False, "message": "Not implemented for this type of device"}

    def nvfabric_show_action(self) -> dict[str, str | bool]:
        return {"success": False, "message": "Not implemented for this type of device"}

    def nvue_interfaces(self) -> dict | None:
        return None

    def run(
        self, args: list[str], timeout: int | None = 15, log_stdout: bool = True, env: dict[str, str] | None = None
    ) -> tuple[bool, str | None]:
        return Script(self._logger).run(args, timeout, log_stdout, env=env)

    @property
    def hostname(self) -> str:
        return self._cmdaemon._lite_node.get("hostname", "localhost")

    @property
    def ip(self) -> str:
        return self._cmdaemon.get_ip()

    @property
    def username(self) -> str | None:
        access_settings = self._cmdaemon.access_settings
        if bool(access_settings):
            return access_settings["username"]
        return None

    @property
    def password(self) -> str | None:
        access_settings = self._cmdaemon.access_settings
        if bool(access_settings):
            return access_settings["password"]
        return None

    @property
    def rest_port(self) -> int:
        access_settings = self._cmdaemon.access_settings
        if bool(access_settings):
            return access_settings["rest_port"]
        return 8765

    @property
    def port_speeds(self) -> dict[str, int] | None:
        return None
