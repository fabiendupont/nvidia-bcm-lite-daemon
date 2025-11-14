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
from random import randint
from random import random
from uuid import UUID

from cm_lite_daemon.object_to_json_encoder import Object_To_JSON_Encoder

try:
    from cm_lite_daemon.device.device import Device
except ImportError:
    from device import Device


class FakeSwitch(Device):
    @property
    def switch_overview(self):
        self._logger.info("Get switch overview")
        ports = []
        names = self.names()
        if bool(names):
            macs = self.macs()
            speeds = self.speeds()
            states = self.states()
            uplinks = self._cmdaemon._lite_node.get("uplinks", [])
        for index, name in names.items():
            ports.append(
                {
                    "baseType": "GuiSwitchPort",
                    "port": index,
                    "name": name,
                    "status": states.get(index, "UNDEFINED"),
                    "speed": speeds.get(index, 0),
                    "detected": macs.get(index, []),
                    "uplink": index in uplinks,
                }
            )
        fake = [
            [
                {"name": "Port", "value": i},
                {"name": "Random", "value": randint(0, 10)},
                {"name": "Duration", "unit": "s", "value": randint(10, 10000)},
                {"name": "Percent", "unit": "%", "value": random()},
                {"name": "Speed", "unit": "B/s", "value": randint(10000000, 10000000000)},
                {"name": "Hello", "value": "World"},
            ]
            for i in range(len(ports))
        ]
        return {
            "baseType": "GuiSwitchOverview",
            "ref_switch_uuid": self._cmdaemon.uuid,
            "model": f"{self.model()}/{self._get_prefix()}",
            "ports": ports,
            "info": {"fake": fake},
        }

    def get_port_by_mac(self, mac: str) -> tuple[int | None, int | None]:
        """
        get the port number of the supplied mac if it exists
        """
        mac = mac.lower()
        macs = self.macs()
        port = next((port for port, macs in macs.items() if mac.lower() in macs), None)
        if port is not None:
            self._logger.debug(f"mac: {mac}, port: {port}")
            return int(port), -1
        self._logger.debug(f"unable to find mac: {mac}, macs: {len(macs)}")
        return None, None

    def model(self):
        return "FakeSwitch"

    def highest_port(self):
        """
        get the highest port number
        """
        return 24

    def _port_numbers(self):
        """
        lost of port numbers: 1 to high
        """
        return list(range(1, self.highest_port() + 1))

    def _get_prefix(self):
        uuid = self._cmdaemon.uuid
        return f"{uuid.bytes[0]:02x}:{uuid.bytes[1]:02x}:{uuid.bytes[2]:02x}"

    def _get_mac(self, port):
        """
        Fake mac for a given port
        """
        return f"fa:ce:{self._get_prefix()}:{port:02d}"

    def macs(self):
        """
        get the list of macs
        <port> [<mac>, ...]
        """
        return {port: [self._get_mac(port)] for port in self._port_numbers()}

    def names(self):
        """
        get the port numbers and names
        """
        return {port: f"fake{port}" for port in self._port_numbers()}

    def speeds(self):
        """
        get the port speeds in b/s
        """
        return {port: 1000000000 for port in self._port_numbers()}

    def states(self):
        """
        print the port states
        """
        return {port: "UP" for port in self._port_numbers()}


def main() -> None:
    """
    Testing only
    """

    class CMDaemon:
        def __init__(self):
            self._lite_node = {"ip": "10.209.20.100"}

        @property
        def snmp_settings(self):
            return {"readString": "public"}

        def uuid(self):
            return UUID(int=1234)

    import logging

    logging.basicConfig(
        level=logging.DEBUG, format="%(levelname)-8s (%(asctime)-15s) [%(filename)-20s:%(lineno)3d] %(message)s"
    )
    logger = logging.getLogger("cm-lite-daemon")

    cmdaemon = CMDaemon()
    device = FakeSwitch(cmdaemon, logger)
    print(json.dumps(device.switch_overview, cls=Object_To_JSON_Encoder, indent=2))


if __name__ == "__main__":
    main()
