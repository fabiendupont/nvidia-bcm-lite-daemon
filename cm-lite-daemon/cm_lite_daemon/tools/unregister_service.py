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

from cm_lite_daemon.tools.exit_codes import ExitCodes
from cm_lite_daemon.tools.os_info import OS_Info


def unregister_service(settings, logger, root):
    os_info = OS_Info(logger)
    if os_info.service == OS_Info.SERVICE_SYSTEMD:
        service = "cm-lite-daemon.service"
        commands = [
            f"/bin/systemctl stop {service}",
            f"/bin/systemctl disable {service}",
        ]
        if os_info.legacy_path is not None:
            try:
                os.remove(os_info.legacy_path + "/debugon")
                os.remove(os_info.legacy_path + "/debugoff")
                os.rmdir(os_info.legacy_path)
            except Exception as e:
                logger.warning(e)
    elif os_info.service == OS_Info.SERVICE_SYSTEMD:
        service = "cm-lite-daemon"
        destination = f"/etc/init.d/{service}"
        commands = [
            f"{destination} start",
            f"/sbin/chkconfig {service} off",
            f"/sbin/chkconfig --del {service}",
        ]
    else:
        return ExitCodes.NOT_FOUND

    for cmd in commands:
        logger.info(f"Run {cmd}")
        if os.system(cmd) != 0:
            return ExitCodes.COMMAND_FAILED

    return ExitCodes.OK
