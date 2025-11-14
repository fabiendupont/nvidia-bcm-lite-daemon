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


class LLDP:
    def __init__(self, cmdaemon, logger, timeout: int = 15):
        self._cmdaemon = cmdaemon
        self._logger = logger
        self.timeout = timeout
        self.path = next(
            (
                it
                for it in ("/usr/sbin/lldpcli", "/sbin/lldpcli", "/usr/bin/lldpcli", "/bin/lldpcli")
                if os.path.exists(it)
            ),
            "lldpcli",
        )

    @property
    def info(self) -> list[dict[str, str | float]] | None:
        try:
            if bool(self._cmdaemon.fake.lldp) and os.path.exists(self._cmdaemon.fake.lldp):
                self._logger.info(f"Gather LLDP info from: {self._cmdaemon.fake.lldp}")
                with open(self._cmdaemon.fake.lldp) as fd:
                    data = json.load(fd)
            elif bool(self.path):
                self._logger.info("Gather LLDP info via lldpcli")
                success, data = Script(self._logger).run(
                    [self.path, "show", "neighbors", "-f", "json"],
                    self.timeout,
                    False,
                    env=self._cmdaemon.venv_free_environment,
                )
                if success:
                    data = json.loads(data)
                else:
                    return None
            else:
                return None

            def get_first_value(data: list[dict[str, str | float]] | None, key: str = "value") -> str | float:
                if isinstance(data, list):
                    for it in data:
                        if isinstance(it, dict) and key in it:
                            return it.get(key)
                return ""

            all_info = []
            for it in data.get("lldp", []):
                for jt in it.get("interface"):
                    device = jt.get("name", "")
                    age = jt.get("age", "")
                    port = jt.get("port", [])
                    chassis = jt.get("chassis", [])
                    for kt in chassis:
                        mac = get_first_value(kt.get("id", None))
                        if mac is None:
                            continue
                        info = [
                            {"name": "Port", "value": device},
                            {"name": "Peer", "value": get_first_value(kt.get("name", None))},
                            {"name": "Peer IP", "value": get_first_value(kt.get("mgmt-ip", None))},
                            {"name": "Peer MAC", "value": mac},
                            {"name": "Description", "value": get_first_value(kt.get("descr", None))},
                            {"name": "Uptime", "value": age},
                        ]
                        for pt in port:
                            if get_first_value(pt.get("id", None)) == mac or (len(port) == 1 and len(chassis) == 1):
                                info += [
                                    {"name": "Peer port", "value": get_first_value(pt.get("descr", ""))},
                                ]
                        all_info.append(info)

            self._logger.info(f"LLDP info, defined {len(all_info)}")
            return all_info
        except Exception as e:
            self._logger.info(f"LLDP info failed: {e}")
            return None

    @property
    def connections(self) -> dict[str, bool | str | dict[str, str]]:
        """
        Keep in sync with cmdaemon/lldp.cpp
        """
        try:
            if bool(self._cmdaemon.fake.lldp) and os.path.exists(self._cmdaemon.fake.lldp):
                self._logger.info(f"Gather LLDP info from: {self._cmdaemon.fake.lldp}")
                with open(self._cmdaemon.fake.lldp) as fd:
                    data = json.load(fd)
            elif bool(self.path):
                self._logger.info("Gather LLDP info via lldpcli")
                success, data = Script(self._logger).run(
                    [self.path, "show", "neighbors", "-f", "json"],
                    self.timeout,
                    False,
                    env=self._cmdaemon.venv_free_environment,
                )
                if success:
                    data = json.loads(data)
                else:
                    return {"node": self._cmdaemon.uuid, "success": False, "error": "failed to run lldpcli"}
            else:
                return {"node": self._cmdaemon.uuid, "success": False, "error": "unable to find lldpcli"}
            result = {"node": self._cmdaemon.uuid, "success": True}
            hostname = self._cmdaemon.hostname
            ports = []
            if json_lldp := data.get("lldp", None):
                if json_interfaces := json_lldp.get("interface", None):
                    if isinstance(json_interfaces, dict):
                        # KDR: some versions have extra [ ] around it
                        json_interfaces = [json_interfaces]
                    for json_interface in json_interfaces:
                        port = ""
                        chassis = ""
                        for interface, info in json_interface.items():
                            if json_chassis := info.get("chassis", None):
                                for name, _ in json_chassis.items():
                                    idx = name.find(".")
                                    chassis = name if idx < 0 else name[0:idx]
                                    break
                            if json_port := info.get("port", None):
                                if json_id := json_port.get("id", None):
                                    port = json_id.get("value", port)
                                if not bool(port):
                                    port = json_port.get("description", port)
                                if not bool(port):
                                    port = json_port.get("descr", port)
                            # KDR may need some changes as this is the switch
                            ports.append(
                                {
                                    "node": hostname,
                                    "interface": interface,
                                    "switch": chassis,
                                    "port": port,
                                }
                            )
            self._logger.info(f"Gathered LLDP info via lldpcli, ports: {len(ports)}")
            result["data"] = ports
            return result
        except Exception as e:
            self._logger.info(f"LLDP connections failed: {e}")
            return {"node": self._cmdaemon.uuid, "success": False, "error": str(e)}
