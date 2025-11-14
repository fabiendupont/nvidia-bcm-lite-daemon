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
import re

from cm_lite_daemon.script import Script


class ARP:
    _re_arp = re.compile(r"^([0-9\.]+)\s+(\w+)\s+([0-9a-zA-Z:]+)\s+(\w+)\s+(.*)$")

    def __init__(self, cmdaemon, logger, timeout: int = 15):
        self._cmdaemon = cmdaemon
        self._logger = logger
        self.timeout = timeout
        self.path = next(
            (it for it in ("/usr/sbin/arp", "/sbin/arp", "/usr/bin/arp", "/bin/arp") if os.path.exists(it)),
            None,
        )

    def info(self, mac_to_interface: dict[str, str]) -> list[dict[str, str]] | None:
        try:
            if bool(self._cmdaemon.fake.arp) and os.path.exists(self._cmdaemon.fake.arp):
                self._logger.info(f"Gather ARP info from: {self._cmdaemon.fake.arp}")
                with open(self._cmdaemon.fake.arp) as fd:
                    data = json.load(fd)
            elif bool(self.path):
                self._logger.info("Gather ARP info via arp")
                success, data = Script(self._logger).run(
                    [self.path, "-n"], self.timeout, False, env=self._cmdaemon.venv_free_environment
                )
                if not success:
                    return None
                lines = [it.strip() for it in data.split("\n")]
            else:
                return None

            all_info = []
            for line in lines[1:]:
                if match := self._re_arp.match(line):
                    info = [
                        {"name": "IP", "value": match[1]},
                        {"name": "Hardware", "value": match[2]},
                        {"name": "Address", "value": match[3]},
                        {"name": "Flags", "value": match[4]},
                        {"name": "Interface", "value": match[5]},
                        {"name": "Port", "value": mac_to_interface.get(match[3], "")},
                    ]
                    all_info.append(info)

            self._logger.info(f"ARP info, defined {len(all_info)}")
            return all_info
        except Exception as e:
            self._logger.info(f"ARP info failed: {e}")
            return None
