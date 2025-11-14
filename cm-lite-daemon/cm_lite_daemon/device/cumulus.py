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

from cm_lite_daemon.device.arp import ARP
from cm_lite_daemon.device.bgp import BGP
from cm_lite_daemon.device.lldp import LLDP
from cm_lite_daemon.device.netlink import Netlink
from cm_lite_daemon.device.ptm import PTM
from cm_lite_daemon.device.switch import Switch
from cm_lite_daemon.util import next_period


class Cumulus(Switch):
    system: str = "system"
    bridge: str = "bridge/domain"
    include_type: set[str] = {"swp"}
    re_include_nics = re.compile(r"^swp(\d+)(?:s(\d+))?$")
    re_name_number = re.compile(r"^([A-Z]+)([0-9]+)$", re.I)
    autoprovision = "/var/log/autoprovision"
    ptm_topology_file = "/etc/ptm.d/topology.dot"

    def __init__(self, cmdaemon, logger):
        super().__init__(cmdaemon, logger)
        self.netlink = Netlink(cmdaemon, logger)
        self.netlink.start()

    def stop(self) -> None:
        super().stop()
        self.netlink.stop()

    def do_maintenance(self) -> None:
        super().do_maintenance()
        if next_period(int(time.time()), 60, 86400):
            self.nv.load_async()

    def show_ptm_topology(self) -> tuple[int, str, str]:
        if not os.path.exists(self.ptm_topology_file):
            return 1, "", f"{self.ptm_topology_file} not found"
        with open(self.ptm_topology_file) as fd:
            return 0, fd.read(), ""

    def apply_ptm_topology(self, data: str | None) -> tuple[int, str, str]:
        if data is None:
            return 1, "", "No content provided"
        try:
            with open(self.ptm_topology_file, "w") as fd:
                fd.write(data)
            code = self._cmdaemon.reload_os_service("ptmd")
            if code <= -100:
                return code, "Updated", "ptmd service not configured"
            elif code:
                return code, "Updated", "failed to reload"
            else:
                return code, "Updated", ""
        except Exception as e:
            return 3, "", str(e)

    def ztp_info(self) -> dict | None:
        self._logger.debug("Get ZTP information")
        success, data = self.run([self.ztp, "-j"], log_stdout=False, env=self._cmdaemon.venv_free_environment)
        if success:
            return json.loads(data)
        else:
            self._logger.info(f"Unable to get ZTP information: {data}")
        return None

    def check_ztp(self) -> None:
        ztp_settings = self._cmdaemon.ztp_settings
        if not ztp_settings:
            return
        success, data = self.run([self.ztp, "-j"], log_stdout=False, env=self._cmdaemon.venv_free_environment)
        if success:
            desired = ztp_settings.get("runZtpOnEachBoot", False)
            status = json.loads(data)
            state = status.get("state", None)
            if state == "enabled":
                if not desired:
                    self.disable_ztp()
                    self._ztp_checked = True
                    self._cmdaemon._sys_info_dirty = True
            elif state == "disabled":
                if desired:
                    if status.get("method", "") in ("ZTP LOCAL", "Switch manually configured"):
                        self.reset_ztp()
                    else:
                        self.enable_ztp()
                    self._ztp_checked = True
                    self._cmdaemon._sys_info_dirty = True
            elif state.lower() == "in progress":
                self._logger.info("ZTP in progress")
                self._ztp_checked = False
            else:
                self._logger.debug(f"ZTP state unhandled: {state}")
        else:
            self._ztp_checked = False

    def disable_ztp(self) -> bool:
        self._logger.debug("Disable ZTP")
        success, _ = self.run([self.ztp, "-d"], log_stdout=False, env=self._cmdaemon.venv_free_environment)
        return success

    def enable_ztp(self) -> bool:
        self._logger.debug("Enable ZTP")
        success, _ = self.run([self.ztp, "-e"], log_stdout=False, env=self._cmdaemon.venv_free_environment)
        return success

    def reset_ztp(self) -> bool:
        self._logger.info("Reset ZTP")
        success, _ = self.run([self.ztp, "--reset"], log_stdout=False, env=self._cmdaemon.venv_free_environment)
        return success

    def __name_number(self, name: str) -> tuple[str, int]:
        match = self.re_name_number.match(name)
        if match:
            return match[1], int(match[2])
        return name, 0

    def _interfaces(self) -> tuple[list[dict[str, typing.Any]], dict[str, list[str]], list[str]]:
        data = self.nvue_get("interface")
        if bool(data):
            bonds = {}
            peerlinks = []
            interfaces = {}
            member_to_bond = {}
            for name, interface in data.items():
                interface_type = interface.get("type", None)
                if interface_type in self.include_type:
                    interface["name"] = name
                    interfaces[self.__name_number(name)] = interface
                elif interface_type == "bond":
                    if bond := interface.get("bond", None):
                        if members := bond.get("member", None):
                            members = members.keys()
                            if name == "peerlink":
                                peerlinks += members
                            else:
                                for member in members:
                                    member_to_bond[self.__name_number(member)] = name
                                bonds[name] = members
                        else:
                            self._logger.info(f"interface {name} has no member information")
                    else:
                        self._logger.info(f"interface {name} has no bond information")
            for member, bond in member_to_bond.items():
                if interface := interfaces.get(member, None):
                    interface["bond"] = bond
            return [interface for _, interface in sorted(interfaces.items())], bonds, peerlinks
        return [], {}, []

    def _bridges(self) -> list[str]:
        if data := self.nvue_get(self.bridge):
            return data.keys()
        return []

    def _bridge_interface_macs(self, bridges: list[str] | None = None) -> dict[str, set[str]]:
        if bridges is None:
            bridges = self._bridges()
        all_bridge_interface_macs = {}
        for bridge in bridges:
            for interface, macs in self._bridge_macs(bridge).items():
                if interface in all_bridge_interface_macs:
                    all_bridge_interface_macs[interface].update(macs)
                else:
                    all_bridge_interface_macs[interface] = macs
        return all_bridge_interface_macs

    def _bridge_macs(self, bridge: str) -> dict[str, set[str]]:
        all_bridge_interface_macs = {}
        data = self.nvue_get(f"{self.bridge}/{bridge}/mac-table?rev=operational")
        if not data:
            return all_bridge_interface_macs
        for _, info in data.items():
            if interface := info.get("interface", None):
                if mac := info.get("mac", None):
                    if interface in all_bridge_interface_macs:
                        all_bridge_interface_macs[interface].add(mac.lower())
                    else:
                        all_bridge_interface_macs[interface] = set([mac.lower()])
        return all_bridge_interface_macs

    def get_port_by_mac(self, mac: str) -> tuple[int | None, int | None]:
        """
        get the port number of the supplied mac if it exists
        """
        mac = mac.lower()
        interfaces, bonds, _ = self._interfaces()
        interface_macs = self._bridge_interface_macs()
        for interface, macs in interface_macs.items():
            if mac in macs:
                if match := self.re_include_nics.match(interface):
                    self._logger.debug(f"mac: {mac}, port: {interface}")
                    return int(match[1]), -1 if match[2] is None else int(match[2])
                if bond_members := bonds.get(interface, None):
                    for member in bond_members:
                        if match := self.re_include_nics.match(member):
                            self._logger.debug(f"mac: {mac}, port: {member}, bond: {interface}")
                            return int(match[1]), -1 if match[2] is None else int(match[2])
        for interface in interfaces:
            if mac == interface.get("link").get("mac", ""):
                _, index = self.__name_number(interface.get("name"))
                self._logger.debug(f"mac: {mac}, port: {index}")
                return index, -1
        self._logger.debug(
            f"unable to find mac: {mac}, macs: {len(interface_macs)}, interface: {len(interfaces)}, bonds: {len(bonds)}"
        )
        return None, None

    @property
    def port_speeds(self) -> dict[str, int] | None:
        interfaces, _, _ = self._interfaces()
        port_speeds = {}
        for interface in interfaces:
            name = interface.get("name")
            link = interface.get("link", {})
            port_speeds[name] = self._speed_to_mb_per_second(link.get("speed", 0))
        return port_speeds

    @property
    def switch_overview(self) -> dict[str, typing.Any]:
        ports: list[dict[str, typing.Any]] = []
        uplinks: list[int] = self._cmdaemon._lite_node.get("uplinks", [])
        all_bridge_interface_macs = self._bridge_interface_macs()
        interfaces, _, peerlinks = self._interfaces()
        mac_to_interface = {}
        for interface in interfaces:
            name = interface.get("name")
            link = interface.get("link", {})
            macs = all_bridge_interface_macs.get(name, [])
            if bond := interface.get("bond", None):
                macs += all_bridge_interface_macs.get(bond, [])
            macs = list(sorted(set(it for it in macs if it != link.get("mac", ""))))
            for mac in macs:
                mac_to_interface[mac] = name
            _, index = self.__name_number(name)
            extra_values = None
            if ifindex := interface.get("ifindex", None):
                extra_values = {"ifindex": ifindex}
            ports.append(
                {
                    "baseType": "GuiSwitchPort",
                    "port": index,
                    "name": name,
                    "status": self._get_state(link.get("state", None), link.get("oper-status", None)),
                    "speed": self._speed_to_mb_per_second(link.get("speed", 0)),
                    "detected": macs,
                    "uplink": index in uplinks or name in peerlinks,
                    "extra_values": extra_values,
                }
            )
        info = {"vrf": self._vrf}
        lldp = LLDP(self._cmdaemon, self._logger).info
        if lldp is not None:
            info["lldp"] = lldp
        bgp = BGP(self._cmdaemon, self._logger).info
        if bgp is not None:
            info["bgp"] = bgp
        ptm = PTM(self._cmdaemon, self._logger).info
        if ptm is not None:
            info["ptm"] = ptm
        arp = ARP(self._cmdaemon, self._logger).info(mac_to_interface)
        if arp is not None:
            info["arp"] = arp
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
