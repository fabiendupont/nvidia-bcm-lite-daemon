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
import sys

from cm_lite_daemon.tools.exit_codes import ExitCodes
from cm_lite_daemon.tools.file_writer import file_writer
from cm_lite_daemon.tools.os_info import OS_Info


def enable_systemd_service(logger, run_env):
    service = "cm-lite-daemon.service"
    replace = {"RUN_ENV": run_env}
    filename = f"/usr/lib/systemd/system/{service}"
    if not file_writer(filename, filename, replace, mode=0o644):
        logger.warning(f"Unable to change RUN_ENV in {filename}")
        return ExitCodes.SAVE_FAILED

    for cmd in [
        "/usr/bin/systemctl daemon-reload",
        f"/bin/systemctl enable {service}",
        f"/bin/systemctl start {service}",
    ]:
        logger.info(f"Run {cmd}")
        if os.system(cmd) != 0:
            return ExitCodes.COMMAND_FAILED
    return ExitCodes.OK


def register_service(settings, logger, root, run_env, multiple=None):
    os_info = OS_Info(logger)
    files = [
        (
            f"{root}/etc/cm-lite-daemon.env.in",
            f"{root}/etc/cm-lite-daemon.env",
            0o600,
        )
    ]
    pidfile = "/var/run/cm-lite-daemon.pid"
    if os_info.service == OS_Info.SERVICE_SYSTEMD:
        if multiple:
            service = f"cm-lite-daemon-{multiple}.service"
            pidfile = f"/var/run/cm-lite-daemon-{multiple}.pid"
        else:
            service = "cm-lite-daemon.service"
        commands = [
            f"/bin/systemctl enable {service}",
            f"/bin/systemctl start {service}",
        ]
        files.append(("service/systemd", f"/usr/lib/systemd/system/{service}", 0o644))
        if os_info.legacy_path is not None:
            try:
                os.mkdir(os_info.legacy_path)
                for name in ["debugoff", "debugon"]:
                    files.append(
                        (
                            f"service/legacy.{name}",
                            f"{os_info.legacy_path}/{name}",
                            0o755,
                        )
                    )
            except Exception as e:
                logger.warning(e)
    elif os_info.service == OS_Info.SERVICE_SYSV:
        service = "cm-lite-daemon"
        destination = f"/etc/init.d/{service}"
        commands = [
            f"/sbin/chkconfig --add {service}",
            f"/sbin/chkconfig {service} on",
            f"{destination} start",
        ]
        files.append(("service/sysv", destination, 0o755))
    else:
        return ExitCodes.NOT_FOUND

    python_path = os.path.dirname(sys.executable)
    replace = {
        "ROOT": root,
        "RUN_ENV": run_env,
        "PIDFILE": pidfile,
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "PYTHON_PATH": python_path,
    }
    for source, destination, mode in files:
        if not file_writer(source, destination, replace, mode=mode):
            logger.warning(f"Unable to save {destination} from {source}")
            return ExitCodes.SAVE_FAILED
        logger.info(f"Saved {destination} from {source}")

    for cmd in commands:
        logger.info(f"Run {cmd}")
        if os.system(cmd) != 0:
            return ExitCodes.COMMAND_FAILED

    return ExitCodes.OK
