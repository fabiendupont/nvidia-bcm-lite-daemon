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


from cm_lite_daemon.http_connection import HTTP_Connection
from cm_lite_daemon.tools.exit_codes import ExitCodes
from cm_lite_daemon.ws_connection import WS_Connection


def check_connectivity(settings, logger):
    try:
        logger.info("### https ###")
        connection = HTTP_Connection(settings, logger)
        version = connection.get_version()
        if version is not None:
            logger.info(f"Version:  {version['cmdaemonVersion']}")
            logger.info(f"Database: {int(version['databaseVersion'])}")
            logger.info(f"Build:    {version['cmdaemonBuildIndex']}")
            logger.info(f"Hash:     {version['cmdaemonBuildHash']}")
    except Exception as e:
        logger.warning(f"Error getting version via HTTP: {str(e)}")
        return ExitCodes.HTTP_CONNECTION

    try:
        logger.info("### websocket ###")
        connection = WS_Connection(settings, logger)
        if connection.run():
            version = connection.get_version()
            if version is not None:
                logger.info(f"Version:  {version['cmdaemonVersion']}")
                logger.info(f"Database: {int(version['databaseVersion'])}")
                logger.info(f"Build:    {version['cmdaemonBuildIndex']}")
                logger.info(f"Hash:     {version['cmdaemonBuildHash']}")
            connection.stop()
    except Exception as e:
        logger.warning(f"Error getting version via WebSocket: {str(e)}")
        return ExitCodes.WS_CONNECTION

    return ExitCodes.OK
