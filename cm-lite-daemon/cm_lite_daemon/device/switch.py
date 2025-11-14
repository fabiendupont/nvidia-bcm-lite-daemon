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
import re
import time
import typing

import requests

from cm_lite_daemon.device.device import Device
from cm_lite_daemon.device.nv import NV
from cm_lite_daemon.util import next_period


class Switch(Device):
    re_speed = re.compile(r"^([0-9\.]+)([KMGT])$", re.I)

    def __init__(self, cmdaemon, logger):
        super().__init__(cmdaemon, logger)
        if bool(self._cmdaemon.fake.ztp):
            self.ztp = self._cmdaemon.fake.ztp
        else:
            for path in ("/usr/sbin", "/usr/bin", "/sbin", "/bin"):
                self.ztp = f"{path}/ztp"
                if os.path.exists(self.ztp):
                    break
        self._ztp_checked = False
        self.nv = NV(cmdaemon, logger)
        self.nv.load_async()

    def stop(self) -> None:
        self.check_ztp()

    def check_ztp(self) -> None:
        pass

    def do_maintenance(self) -> None:
        next_day = next_period(int(time.time()), 60, 86400)
        if next_day or not self._ztp_checked:
            self.check_ztp()

    def sync_log(self, path: bool = False) -> str:
        if path:
            return self.autoprovision
        if not os.path.exists(self.autoprovision):
            return f"{self.autoprovision} does not exist"
        with open(self.autoprovision) as fd:
            return fd.read()

    def commands(self, force: bool = False) -> dict | None:
        if force:
            self.nv.load_async()
            self.nv.wait()
        return self.nv.serialize()

    def diff_commands(self) -> tuple[int, dict | None, str]:
        return self.nv.diff()

    def show_commands(self) -> tuple[int, dict | None, str]:
        return self.nv.show()

    def show_commands_yaml(self) -> tuple[int, str, str]:
        return self.nv.show_yaml()

    def save_commands(self) -> tuple[int, str, str]:
        return self.nv.save()

    def detach_commands(self) -> tuple[int, str, str]:
        return self.nv.detach()

    def apply_commands(self, staged: bool = False, stage_only: bool = False) -> tuple[int, str, str]:
        return self.nv.apply(staged, stage_only)

    def show_system_ztp(self) -> dict[str, str | bool]:
        args = [self.nv.nv, "show", "system", "ztp", "-o", "json"]
        success, data = self.run(args, env=self._cmdaemon.venv_free_environment)
        return {"success": success, "message": data}

    @property
    def _vrf(self) -> dict[str, str | int] | None:
        return self.nv.vrf()

    def _get_state(self, state: dict[str, typing.Any] | None, oper_state: str | None = None) -> str:
        if bool(oper_state):
            return oper_state.upper()
        if bool(state):
            if "down" in state:
                return "DOWN"
            return "UP"
        return "UNKNOWN"

    def _speed_to_mb_per_second(self, text: str | int) -> int:
        if isinstance(text, int):
            return text
        match = self.re_speed.match(text)
        if match:
            value = float(match[1])
            if match[2] in ("G", "g"):
                value *= 1000000000
            elif match[2] in ("T", "t"):
                value *= 1000000000000
            elif match[2] in ("M", "m"):
                value *= 1000000
            elif match[2] in ("K", "k"):
                value *= 1000
            return int(value)
        return int(text)

    def platform(self) -> tuple[str, str, str]:
        success, data = self.run(
            [self.nv.nv, "--output", "json", "show", "platform"],
            env=self._cmdaemon.venv_free_environment,
            log_stdout=False,
        )
        if not success:
            return "failed to run: nv show platform", "", ""
        try:
            data = json.loads(data)
            return (
                data.get("serial-number", "unknown"),
                data.get("part-number", "unknown"),
                data.get("product-name", "unknown"),
            )
        except Exception:
            return "parse error", "", ""

    def product(self) -> dict[str, str] | None:
        success, data = self.run(
            [self.nv.nv, "--output", "json", "show", "system"],
            env=self._cmdaemon.venv_free_environment,
            log_stdout=False,
        )
        if not success:
            return None
        try:
            data = json.loads(data)
            return {
                "Name": data.get("product-name", "unknown"),
                "Release": data.get("product-release", "unknown"),
            }
        except Exception:
            return None

    def ztp_info(self) -> None:
        return None

    def sdn_info(self) -> None:
        return None

    def chassis(self) -> None:
        return None

    def sys_info(self) -> dict[str, dict[str, dict]] | None:
        ztp = self.ztp_info()
        sdn = self.sdn_info()
        chassis = self.chassis()
        product = self.product()
        if not bool(ztp) and not bool(sdn) and not bool(product) and not bool(chassis):
            return None
        sys_info = {}
        if bool(ztp):
            sys_info["ztp"] = {"ZTP": ztp}
        if bool(sdn):
            sys_info["sdn"] = {"SDN": sdn}
        if bool(chassis):
            sys_info["chassis"] = {"Chassis": chassis}
        if bool(product):
            sys_info["product"] = {"Product": product}
        return {"local": sys_info}

    def nvue_get(self, path: str) -> dict[str, typing.Any] | None:
        rest_port = self.rest_port
        if rest_port == 0:
            return None
        url = f"https://localhost:{rest_port}/nvue_v1/{path}"
        self._logger.info(f"Get url: {url}")
        try:
            result = requests.get(url, auth=(self.username, self.password), verify=False)
            if result.status_code == 200:
                return result.json()
            else:
                self._logger.warning(f"Unable to read data from {url} using {self.username}")
        except Exception as e:
            self._logger.warning(f"Unable to read data from {url}, error: {e}")
        return None
