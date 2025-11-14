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


class Fake:
    def __init__(self, logger, hostname: str | None = None):
        self.nv = None
        self.ztp = None
        self.arp = None
        self.bgp = None
        self.ptm = None
        self.lldp = None
        if os.path.exists("/root/.fake.switch"):
            self.nv = "/root/bin/switch/nv"
            self.ztp = "/root/bin/switch/ztp"
            self.arp = "/root/.fake.arp"
            self.bgp = "/root/.fake.bgp"
            self.ptm = "/root/.fake.ptm"
            self.lldp = "/root/.fake.lldp"
            with open("/root/.fake.switch") as fd:
                try:
                    for key, value in json.load(fd).items():
                        if bool(hostname):
                            value = value.replace("${hostname}", hostname)
                        setattr(self, key, value)
                except Exception as e:
                    logger.info(f"Fake, parse error: {e}")
            logger.info(f"Fake NV: {self.nv}")
            logger.info(f"Fake ZTP: {self.ztp}")
            logger.info(f"Fake ARP: {self.arp}")
            logger.info(f"Fake BGP: {self.bgp}")
            logger.info(f"Fake PTM: {self.ptm}")
            logger.info(f"Fake LLDP: {self.lldp}")
