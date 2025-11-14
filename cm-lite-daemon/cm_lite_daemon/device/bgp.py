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


class BGP:
    def __init__(self, cmdaemon, logger, protocols: list[str] | None = None, timeout: int = 15):
        self._cmdaemon = cmdaemon
        self._logger = logger
        if protocols is None:
            self.protocols = ["ipv4", "ipv4Unicast"]
        else:
            self.protocols = protocols
        self.timeout = timeout
        self.vtysh = "vtysh"
        for path in ("/usr/sbin", "/usr/bin", "/sbin", "/bin"):
            self.vtysh = f"{path}/vtysh"
            if os.path.exists(self.vtysh):
                break

    @property
    def info(self) -> list[dict[str, str | float]] | None:
        try:
            if bool(self._cmdaemon.fake.bgp) and os.path.exists(self._cmdaemon.fake.bgp):
                self._logger.info(f"Gather BGP info from: {self._cmdaemon.fake.bgp}")
                with open(self._cmdaemon.fake.bgp) as fd:
                    data = json.load(fd)
            else:
                success, data = Script(self._logger).run(
                    [self.vtysh, "-c", "show ip bgp summary json"],
                    self.timeout,
                    False,
                    env=self._cmdaemon.venv_free_environment,
                )
                if success:
                    self._logger.debug(f"BGB, summary length: {len(data)}")
                    data = json.loads(data)
                else:
                    return None

            all_info = []
            for protocol in self.protocols:
                protocol_data = data.get(protocol, None)
                if protocol_data is None:
                    self._logger.debug(f"BGB, protocol not found {protocol}")
                    continue
                asn = protocol_data.get("as")
                router_id = protocol_data.get("routerId")
                vrf_name = protocol_data.get("vrfName")
                peers = protocol_data.get("peers")
                if bool(peers):
                    self._logger.debug(f"BGB, router ID: {router_id}, peers {len(peers)}")
                    for key, value in peers.items():
                        peer_ip = key
                        peer_name = value.get("hostname", None)
                        if peer_name is None:
                            continue
                        peer_state = value.get("state", "")
                        peer_asn = value.get("remoteAs", "")
                        peer_uptime = value.get("peerUptime", "")
                        peer_prefix_received = value.get("pfxRcd", 0)
                        peer_prefix_sent = value.get("pfxSnt", 0)
                        all_info.append(
                            [
                                {"name": "Protocol", "value": protocol},
                                {"name": "ASN", "value": asn},
                                {"name": "Router ID", "value": router_id},
                                {"name": "VRF name", "value": vrf_name},
                                {"name": "Peer IP", "value": peer_ip},
                                {"name": "Peer name", "value": peer_name},
                                {"name": "Peer ASN", "value": peer_asn},
                                {"name": "Peer uptime", "value": peer_uptime},
                                {"name": "Peer state", "value": peer_state},
                                {"name": "Peer prefix received", "value": peer_prefix_received},
                                {"name": "Peer prefix sent", "value": peer_prefix_sent},
                            ]
                        )
                else:
                    self._logger.debug(f"BGB, router ID: {router_id}, no peers")
                    all_info.append(
                        [
                            {"name": "Protocol", "value": protocol},
                            {"name": "ASN", "value": asn},
                            {"name": "Router ID", "value": router_id},
                            {"name": "VRF name", "value": vrf_name},
                        ]
                    )

            self._logger.info(f"BGP info, defined {len(all_info)}, data: {len(data)}")
            return all_info
        except Exception as e:
            self._logger.info(f"BGP info failed: {e}")
            return None
