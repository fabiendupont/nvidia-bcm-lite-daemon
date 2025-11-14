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
import typing

from natsort import natsorted

from cm_lite_daemon.device.lldp import LLDP
from cm_lite_daemon.device.switch import Switch
from cm_lite_daemon.rpc.ws_request import WS_Request


class NVLinkSwitch(Switch):
    def reboot(self) -> bool:
        success, data = self.run(
            [self.nv.nv, "action", "reboot", "system"],
            env=self._cmdaemon.venv_free_environment,
        )
        self._logger.info(f"reboot: {data}")
        return success

    def shutdown(self) -> bool:
        success, data = self.run(
            [self.nv.nv, "action", "shutdown", "system", "halt"],
            env=self._cmdaemon.venv_free_environment,
        )
        self._logger.info(f"shutdown: {data}")
        return success

    def ztp_info(self) -> dict | None:
        self._logger.debug("Get ZTP information")
        success, data = self.run([self.ztp, "status"], log_stdout=False, env=self._cmdaemon.venv_free_environment)
        if success:
            info = {}
            for line in data.split("\n"):
                idx = line.find(":")
                if idx > 0:
                    key = line[0:idx].replace("ZTP", "").strip()
                    value = line[idx + 1 :].strip()  # noqa: E203
                    info[key] = value
            return info
        else:
            self._logger.info(f"Unable to get ZTP information: {data}")
        return None

    def chassis(self) -> dict | None:
        self._logger.debug("Get platform chassis information")
        success, data = self.run(
            [self.nv.nv, "show", "platform", "chassis", "--output", "json"],
            env=self._cmdaemon.venv_free_environment,
        )
        if success:
            try:
                return json.loads(data)
            except Exception as e:
                self._logger.debug(f"Failed to parse platform chassis: {e}")
        return None

    def sdn_info(self) -> dict | None:
        # TODO, add other files if needed
        self._logger.debug("Get sdn information")
        success, data = self.run(
            [
                self.nv.nv,
                "show",
                "sdn",
                "config",
                "app",
                "nmx-controller",
                "type",
                "fm_config",
                "files",
                "--output",
                "json",
            ],
            env=self._cmdaemon.venv_free_environment,
        )
        if success:
            try:
                data = json.loads(data)
                result = data
                for _, value in data.items():
                    if path := value.get("path", None):
                        with open(path) as fd:
                            line = next((it for it in fd.readlines() if it.startswith("MNNVL_TOPOLOGY")), None)
                            if bool(line):
                                idx = line.find("=") + 1
                                value["topology"] = line[idx:].strip()
                return result
            except Exception as e:
                self._logger.debug(f"Failed to parse sdn config: {e}")
        return None

    def check_ztp(self) -> None:
        ztp_settings = self._cmdaemon.ztp_settings
        if not ztp_settings:
            return
        success, data = self.run([self.ztp, "status"], log_stdout=False, env=self._cmdaemon.venv_free_environment)
        if success:
            desired = ztp_settings.get("runZtpOnEachBoot", False)
            line = next((line for line in data.split("\n") if line.startswith("ZTP Admin Mode")), None)
            state = None
            if line:
                idx = line.find(":")
                if idx > 0:
                    state = line[idx + 1 :].strip()  # noqa: E203
            if state == "True":
                if not desired:
                    self.disable_ztp()
                    self._ztp_checked = True
                    self._cmdaemon._sys_info_dirty = True
            elif state == "False":
                if desired:
                    self.enable_ztp()
                    self._ztp_checked = True
                    self._cmdaemon._sys_info_dirty = True
            else:
                self._logger.debug(f"ZTP state unhandled: {state}")
        else:
            self._ztp_checked = False

    def disable_ztp(self) -> bool:
        self._logger.debug("Disable ZTP")
        success, _ = self.run([self.ztp, "disable", "-y"], log_stdout=False, env=self._cmdaemon.venv_free_environment)
        return success

    def enable_ztp(self) -> bool:
        self._logger.debug("Enable ZTP")
        success, _ = self.run([self.ztp, "enable"], log_stdout=False, env=self._cmdaemon.venv_free_environment)
        return success

    def reset_ztp(self) -> bool:
        self._logger.info("Reset ZTP")
        success, _ = self.run([self.ztp, "erase"], log_stdout=False, env=self._cmdaemon.venv_free_environment)
        if success:
            success = self.enable_ztp()
        return success

    def get_fm_config(self) -> tuple[bool, str]:
        self._logger.info("Get fm_config")
        request = WS_Request(self._cmdaemon._connection)
        request.call("device", "getNvlinkSwitchFMConfig", [self._cmdaemon.uuid])
        result = request.wait()
        if bool(result):
            return result.get("configured", False), result.get("content", "")
        self._logger.info("Failed to get fm_config")
        return False, ""

    def install_fm_config(self) -> tuple[bool, str]:
        configured, content = self.get_fm_config()
        if not configured:
            return True, ""
        if content == "":
            return False, "empty fm_config"
        filename = "/host/cluster_infra/app_config/nmx-controller/fm_config/fm_config.cfg"
        if os.path.exists(filename):
            with open(filename) as fd:
                if fd.read() == content:
                    self._logger.info("Keep fm_config, already correct")
                    return True, ""
        else:
            os.makedirs(os.path.dirname(filename), mode=0o755, exist_ok=True)
        with open(filename, "w") as fd:
            fd.write(content)
        self._logger.info("Install fm_config")
        success, data = self.run(
            [
                self.nv.nv,
                "action",
                "install",
                "sdn",
                "config",
                "app",
                "nmx-controller",
                "type",
                "fm_config",
                "files",
                os.path.basename(filename),
            ],
            env=self._cmdaemon.venv_free_environment,
        )
        if not success:
            self._logger.info("Failed to installed fm_config")
            return False, data
        self._logger.info("Installed fm_config")
        return True, ""

    def factory_reset(self, force: bool) -> dict[str, str | bool]:
        args = [self.nv.nv, "action", "reset", "system", "factory"]
        if force:
            args.append("force")
        success, data = self.run(args, env=self._cmdaemon.venv_free_environment)
        return {"success": success, "message": data}

    def show_sdn_partition(self) -> dict[str, str | bool]:
        args = [self.nv.nv, "--output", "json", "show", "sdn", "partition"]
        success, data = self.run(args, env=self._cmdaemon.venv_free_environment)
        if success:
            try:
                data = json.loads(data)
                self._logger.info(f"Got SDN partition data, partitions: {len(data)}")
                for clique_id, info in data.items():
                    self._logger.info(f"Get SDN partition data: {clique_id}")
                    success, clique_data = self.run(args + [clique_id], env=self._cmdaemon.venv_free_environment)
                    if success:
                        info.update(json.loads(clique_data))
                    else:
                        self._logger.info(f"Failed to get SDN partition {clique_id} data")
            except Exception as e:
                self._logger.info(f"Failed to process SDN partition data: {e}")
        else:
            self._logger.info("Failed to get SDN partition data")
        return {"success": success, "result": data}

    def nvfabric_start(self) -> dict[str, str | bool]:
        success, data = self.run(
            [self.nv.nv, "set", "cluster", "state", "enabled"], env=self._cmdaemon.venv_free_environment
        )
        if not success:
            return {"success": False, "message": data}
        success, data = self.run([self.nv.nv, "config", "apply"], env=self._cmdaemon.venv_free_environment)
        if not success:
            return {"success": False, "message": data}
        success, data = self.install_fm_config()
        if not success:
            return {"success": False, "message": data}
        return {"success": True, "message": ""}

    def nvfabric_stop(self) -> dict[str, str | bool]:
        success, data = self.run(
            [self.nv.nv, "set", "cluster", "state", "disable"], env=self._cmdaemon.venv_free_environment
        )
        if not success:
            return {"success": False, "message": data}
        success, data = self.run([self.nv.nv, "config", "apply"], env=self._cmdaemon.venv_free_environment)
        if not success:
            return {"success": False, "message": data}
        return {"success": True, "message": ""}

    def nvfabric_status(self) -> dict[str, str | bool]:
        success, data = self.run(
            [self.nv.nv, "--output", "json", "show", "cluster", "apps"],
            env=self._cmdaemon.venv_free_environment,
            log_stdout=False,
        )
        if not success:
            return {"success": False, "hostname": self._cmdaemon._hostname, "message": data}
        try:
            apps = json.loads(data)
        except Exception as e:
            return {"success": False, "message": str(e), "hostname": self._cmdaemon._hostname, "data": data}
        nmxc = apps.get("nmx-controller", None)
        if not bool(nmxc):
            return {
                "success": True,
                "leader": False,
                "message": "nmx-controller not started",
                "hostname": self._cmdaemon._hostname,
                "apps": apps,
            }
        if nmxc.get("status", "") == "ok":
            return {
                "success": True,
                "leader": True,
                "hostname": self._cmdaemon._hostname,
                "apps": apps,
            }
        return {
            "success": True,
            "leader": False,
            "hostname": self._cmdaemon._hostname,
            "message": "nmx-controller not ok",
            "apps": apps,
        }

    def nvfabric_health(self) -> dict[str, str | bool]:
        success, data = self.run(
            [self.nv.nv, "--output", "json", "show", "system", "health"],
            env=self._cmdaemon.venv_free_environment,
            log_stdout=False,
        )
        if not success:
            return {"success": False, "message": data}
        try:
            return {"success": True, "health": json.loads(data)}
        except Exception as e:
            return {"success": False, "message": str(e), "data": data}

    def nvfabric_show_action(self) -> dict[str, str | bool]:
        success, data = self.run(
            [self.nv.nv, "--output", "json", "show", "action"],
            env=self._cmdaemon.venv_free_environment,
            log_stdout=False,
        )
        if not success:
            return {"success": False, "message": data}
        try:
            return {"success": True, "health": json.loads(data)}
        except Exception as e:
            return {"success": False, "message": str(e), "data": data}

    def nvue_interfaces(self) -> dict | None:
        # KDR: do NOT use nv command: very slow
        return self.nvue_get("interface")

    @property
    def show_interfaces(self) -> dict | None:
        success, data = self.run(
            [self.nv.nv, "--output", "json", "show", "interface"],
            env=self._cmdaemon.venv_free_environment,
            log_stdout=False,
            timeout=30,
        )
        if not success:
            return None
        return json.loads(data)

    @property
    def port_speeds(self) -> dict[str, int] | None:
        try:
            interfaces = self.show_interfaces
            if interfaces is None:
                return None
        except Exception:
            return None
        return {
            name: self._speed_to_mb_per_second(interface.get("link", {}).get("speed", 0))
            for name, interface in interfaces.items()
        }

    @property
    def switch_overview(self) -> dict[str, typing.Any] | None:
        try:
            interfaces = self.show_interfaces
            if interfaces is None:
                return {
                    "baseType": "GuiSwitchOverview",
                    "ref_switch_uuid": str(self._cmdaemon.uuid),
                    "model": "no data",
                }
        except Exception as e:
            return {
                "baseType": "GuiSwitchOverview",
                "ref_switch_uuid": str(self._cmdaemon.uuid),
                "model": str(e),
            }
        index = 0
        ports = []
        for name in natsorted(interfaces.keys()):
            index += 1
            interface = interfaces.get(name)
            link = interface.get("link", {})
            ports.append(
                {
                    "baseType": "GuiSwitchPort",
                    "port": interface.get("ifindex", index),
                    "name": name,
                    "status": self._get_state(link.get("state", None)),
                    "speed": self._speed_to_mb_per_second(link.get("speed", 0)),
                }
            )
        info = {"vrf": self._vrf}
        lldp = LLDP(self._cmdaemon, self._logger).info
        if lldp is not None:
            info["lldp"] = lldp
        serial_number, part_number, model = self.platform()
        return {
            "baseType": "GuiSwitchOverview",
            "ref_switch_uuid": str(self._cmdaemon.uuid),
            "serialNumber": serial_number,
            "partNumber": part_number,
            "model": model,
            "ports": ports,
            "info": info,
        }
