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


from cm_lite_daemon.rpc.rpc import RPC


def get_network(settings, logger, name):
    rpc = RPC(settings)
    (code, network) = rpc.call(service="cmnet", call="getNetwork", args=[name])
    if code != 0:
        logger.warning("Unable to get network information: %s (%d)", network, code)
        return None
    return network
