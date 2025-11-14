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


def get_mac_ip(if_names=None):
    try:
        import netifaces

        for interface in netifaces.interfaces():
            if interface in ["lo"] or ((if_names is not None) and (interface not in if_names)):
                continue
            info = netifaces.ifaddresses(interface)
            if netifaces.AF_INET in info and netifaces.AF_LINK in info:
                ipv4 = info[netifaces.AF_INET]
                mac = info[netifaces.AF_LINK]
            else:
                continue
            if (len(ipv4) < 1) or (len(mac) < 1):
                continue
            return (mac[0]["addr"], ipv4[0]["addr"])
    except Exception as e:
        print(("Error trying to determine IP: %s", e))
    print("Unable to determine IP")
    return ("00:00:00:00:00:00", "0.0.0.0")
