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


import os
import platform


class OS_Info:
    SERVICE_NONE = 0
    SERVICE_SYSTEMD = 1
    SERVICE_SYSV = 2
    SERVICE_WINDOWS = 3

    def __init__(self, logger):
        self.logger = logger
        self.service = self.SERVICE_NONE
        self.legacy_path = None
        if platform.system() == "Linux":
            if os.path.exists("/var/lib/systemd"):
                self.service = self.SERVICE_SYSTEMD
                for path in [
                    "/usr/lib/initscripts/legacy-actions",
                    "/usr/libexec/initscripts/legacy-actions",
                ]:
                    if os.path.exists(path):
                        self.legacy_path = path + "/cm-lite-daemon"
                        break
                logger.info("System uses systemd")
            elif os.path.exists("/etc/init.d"):
                self.service = self.SERVICE_SYSV
                logger.info("System uses sysv")
            else:
                logger.warning("Unable to determine Linux service type")
        elif platform.system() == "Windows":
            self.service = self.SERVICE_WINDOWS
            logger.info("System uses Windows")
        else:
            logger.warning("Unable to determine service type")
