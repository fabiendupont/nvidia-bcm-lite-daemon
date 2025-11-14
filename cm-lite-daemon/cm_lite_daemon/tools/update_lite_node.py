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
from uuid import uuid4

from cm_lite_daemon.rpc.rpc import RPC
from cm_lite_daemon.tools.exit_codes import ExitCodes
from cm_lite_daemon.tools.find_network import find_network
from cm_lite_daemon.tools.get_network import get_network
from cm_lite_daemon.tools.get_partition import get_partition
from cm_lite_daemon.tools.interface_info import get_mac_ip


def update_lite_node(settings, logger, hostname=None, fake_mac=None, network=None, if_names=None):
    if hostname is None:
        hostname = socket.gethostname().split(".", 1)[0]

    mac, ip = get_mac_ip(if_names)
    if fake_mac is not None:
        mac = fake_mac

    rpc = RPC(settings)
    code, node = rpc.call(service="cmdevice", call="getDevice", args=[hostname])
    if code != 0:
        logger.warning(f"Unable to get node via hostname: {code}")
        return ExitCodes.HTTP_CONNECTION
    if node is None and mac != "00:00:00:00:00:00":
        code, node = rpc.call(service="cmdevice", call="getDevice", args=[mac])
        if code != 0:
            logger.warning(f"Unable to node via mac: {code}")
            return ExitCodes.HTTP_CONNECTION

    if network is None:
        network = find_network(settings, logger, ip)
    else:
        network = get_network(settings, logger)

    if network is None:
        return ExitCodes.NOT_FOUND

    partition = get_partition(settings, logger)
    if partition is None:
        return ExitCodes.NOT_FOUND

    if node is None:
        logger.info("Adding node: %s (%s, %s)", hostname, ip, mac)
        node = {
            "baseType": "Device",
            "childType": "LiteNode",
            "hostname": hostname,
            "uuid": str(uuid4()),
            "mac": mac,
            "partition": partition["uuid"],
            "powerControl": "none",
            "interfaces": [
                {
                    "baseType": "NetworkInterface",
                    "childType": "NetworkPhysicalInterface",
                    "network": network["uuid"],
                    "name": "eth0",
                    "ip": ip,
                }
            ],
        }
        code, response = rpc.call(service="cmdevice", call="addLiteNode", args=[node, 0])
        if code != 0:
            logger.warning(f"Unable to get add node information: {response} {code}")
            return ExitCodes.HTTP_CONNECTION
        elif not response.get('success', False):
            logger.warning("Failed to add a new lite node")
            for error in response["validation"]:
                logger.warning(error["message"])
            return ExitCodes.RPC_ERROR
    elif ip == "0.0.0.0" and mac == "00:00:00:00:00:00":
        logger.info("Unable to determine MAC/IP, not updating")
    elif ip in [it["ip"] for it in node["interfaces"]] and mac == node["mac"]:
        logger.info("No need to update, MAC/IP already correct")
    else:
        logger.info(f"Updating node: {hostname} ({ip}, {mac})")
        node["mac"] = mac
        if bool(node["interfaces"]):
            eth0 = next((it for it in node["interfaces"]), node["interfaces"][0])
            eth0["network"] = network["uuid"]
            eth0["ip"] = ip
        else:
            node["interfaces"] = [
                {
                    "baseType": "NetworkInterface",
                    "childType": "NetworkPhysicalInterface",
                    "network": network["uuid"],
                    "name": "eth0",
                    "ip": ip,
                }
            ]
        if node.get("childType") == "LiteNode":
            code, response = rpc.call(service="cmdevice", call="updateLiteNode", args=[node, 0])
        elif node.get("childType") == "Switch":
            code, response = rpc.call(service="cmdevice", call="updateSwitch", args=[node, 0])
        else:
            logger.warning(f"Failed to find device of the right type: {node.get('childType')}")
            return ExitCodes.NOT_FOUND
        if code != 0:
            logger.warning(f"Unable to update node information: {response} {code}")
            return ExitCodes.HTTP_CONNECTION
        elif not response.get('success', False):
            logger.warning("Failed update lite node information")
            return ExitCodes.RPC_ERROR
    return ExitCodes.OK
