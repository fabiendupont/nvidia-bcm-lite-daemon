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

import math
import os
import re
import socket

import requests

kmg_regex = re.compile(r"^(\d+(\.\d+)?)\s*(\w).*$")
si_prefx = {"K": 1, "M": 2, "G": 3, "T": 4}


def contains(vector: list, element, case_insensitive: bool = True) -> bool:
    if not case_insensitive or not isinstance(element, (str, bytes)):
        return element in vector
    else:
        return element.lower() in [it.lower() for it in vector]


def is_valid_ipv4_address(address: str | None) -> bool:
    if address is None:
        return False
    try:
        socket.inet_pton(socket.AF_INET, address)
    except TypeError:  # address not a str
        return False
    except AttributeError:  # no inet_pton here, sorry
        try:
            socket.inet_aton(address)
        except socket.error:
            return False
        return address.count(".") == 3
    except socket.error:  # not a valid address
        return False
    return True


def parse_kmg(text: str | int, factor: int = 1000, default: int = 1) -> int:
    if isinstance(text, str):
        match = re.search(kmg_regex, text)
        if match is None:
            return int(float(text) * default)
        unit = str(match.group(3))
        return int(float(match.group(1)) * int(math.pow(factor, si_prefx.get(unit.upper(), 1))))
    return text


def wget(url: str, path: str) -> bool:
    try:
        response = requests.get(url, stream=True)
        with open(path, 'wb') as output:
            output.write(response.content)
            return True
    except Exception:  # ??
        return False


def ucfirst(text: str) -> str:
    if bool(text):
        return text[0].upper() + text[1:].lower()
    return text


def next_period(now: int, interval: int, period: int) -> bool:
    return (now % period) > ((now + interval) % period)


def get_mac(name: str) -> str | None:
    filename = f"/sys/class/net/{name}/address"
    if os.path.exists(filename):
        with open(filename) as fd:
            return fd.readline().strip()
    return None
