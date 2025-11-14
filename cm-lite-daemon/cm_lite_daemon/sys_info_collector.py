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


#
# Incomplete, but enough to make most people happy.
#
# Make sure this class remains platform invariant.
# And works regardless of which 3rd party packages have been installed.
#

import re
import time
from uuid import UUID

from cm_lite_daemon.util import parse_kmg


class Sys_Info_Collector:
    _re_ignore_nics = [re.compile(r"^lo$")]
    _re_ignore_disks = [re.compile(r"^/dev/loop\d+$")]

    def __init__(self):
        self.baseType = "SysInfoCollector"
        self.ref_device_uuid = UUID(int=0)
        self.processors = []
        self.disks = []
        self.gpuUnits = []
        self.mics = []
        self.memory = []
        self.biosVersion = ""
        self.biosVendor = ""
        self.biosDate = ""
        self.motherboardManufacturer = ""
        self.motherboardName = ""
        self.memoryTotal = 0
        self.memorySwap = 0
        self.diskCount = 0
        self.diskTotalSpace = 0
        self.osName = ""
        self.osVersion = ""
        self.osFlavor = ""
        self.vendorTag = ""
        self.systemName = ""
        self.systemManufacturer = ""
        self.nics = []
        self.bootIf = ""
        self.interconnects = []
        self.fips = False
        self.seLinux = False
        self.extra = None
        self.timestamp = 0

    def detect(self):
        self.timestamp = int(time.time())
        self._detect_platform()
        self._detect_memory()
        self._detect_disks()
        self._detect_cpu()
        self._detect_nics()
        self._detect_dmidecode()

    def _detect_dmidecode(self):
        try:
            from dmidecode import DMIDecode

            dmi = DMIDecode()
            bios = dmi.get("BIOS")[0]
            self.biosVersion = bios.get("Version", "")
            self.biosVendor = bios.get("Vendor", "")
            self.biosDate = bios.get("Release Data", "")
            self.systemManufacturer = dmi.manufacturer()
            self.systemName = dmi.model()
        except RuntimeError as e:
            self.biosVersion = str(e)
        except ImportError:
            pass

    def _detect_platform(self):
        try:
            import platform

            self.osName = platform.system()
            self.osVersion = platform.release()
            self.osFlavor = platform.version()
        except ImportError:
            pass

    def _detect_memory(self):
        try:
            import psutil

            self.memoryTotal = psutil.virtual_memory().total
            self.swapTotal = psutil.swap_memory().total
        except ImportError:
            pass

    def _detect_disks(self):
        try:
            import psutil

            processed = set()
            self.disks = []
            for disk in psutil.disk_partitions():
                if any(re.match(it, disk.device) is not None for it in self._re_ignore_disks):
                    continue
                if disk.device in processed:
                    continue
                try:
                    usage = psutil.disk_usage(disk.mountpoint)
                    self.disks.append(
                        {
                            "baseType": "DiskInfo",
                            "name": disk.device,
                            "size": usage.total,
                        }
                    )
                    processed.add(disk.device)
                    self.diskTotalSpace += usage.total
                except Exception:
                    pass
            self.diskCount = len(self.disks)
        except ImportError:
            pass

    def _detect_cpu(self):
        try:
            import cpuinfo

            self.processors = []
            info = cpuinfo.get_cpu_info()
            if bool(info["count"]):
                self.processors.append(
                    {
                        "baseType": "Processor",
                        "vendor": info.get("vendor_id_raw", info.get("vendor_id", "")),
                        "model": info.get("brand_raw", info.get("brand", "")),
                        "IDs": list(range(info["count"])),
                        "coreIDs": list(range(info["count"])),
                        "physicalIDs": [0] * info["count"],
                        "speed": info.get("hz_advertised_raw", [0, 0])[0],
                        "cacheSize": parse_kmg(info["l2_cache_size"]),
                    }
                )
        except ImportError:
            pass

    def _detect_nics(self):
        try:
            import psutil

            self.nics = []
            for nic, _ in psutil.net_if_addrs().items():
                if any(re.match(it, nic) is not None for it in self._re_ignore_nics):
                    continue
                if nic == "lo":
                    continue
                self.nics.append(nic)
        except ImportError:
            pass
