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


import socket

from cm_lite_daemon.rpc.rpc import RPC
from cm_lite_daemon.tools.exit_codes import ExitCodes


def remove_lite_node(settings, logger, hostname=None):
    if hostname is None:
        hostname = socket.gethostname().split(".", 1)[0]

    rpc = RPC(settings)
    (code, node) = rpc.call(service="cmdevice", call="getDevice", args=[hostname])
    if code != 0:
        logger.warning("Unable to get %s information: (%d)", hostname, code)
        return ExitCodes.HTTP_CONNECTION
    elif node is None:
        logger.warning("Unable to find lite node definition (%s)", hostname)
        return ExitCodes.NOT_FOUND
    else:
        (code, response) = rpc.call(service="cmdevice", call="removeDevice", args=[node["uuid"], 0])
        if code != 0:
            logger.warning("Unable to get remove node information: %s (%d)", response, code)
            return ExitCodes.HTTP_CONNECTION
        elif not response["success"]:
            logger.warning("Failed remove lite node information")
            return ExitCodes.RPC_ERROR
    return ExitCodes.OK
