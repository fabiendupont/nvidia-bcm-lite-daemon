#
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

import os
import socket
import struct
import threading


class Netlink:
    RTMGRP_LINK = 1

    NLMSG_NOOP = 1
    NLMSG_ERROR = 2

    RTM_NEWLINK = 16
    RTM_DELLINK = 17

    IFLA_IFNAME = 3

    def __init__(self, cmdaemon, logger):
        self._cmdaemon = cmdaemon
        self._logger = logger
        self._socket = None
        self._thread = None
        self._state = None
        self._condition = threading.Condition()

    def start(self) -> bool:
        with self._condition:
            if bool(self._thread):
                self._logger.info("Netlink already started")
                return False
            if bool(self._socket):
                self._logger.info("Netlink socket existed, closing")
                self._socket.close()
            try:
                self._socket = socket.socket(socket.AF_NETLINK, socket.SOCK_RAW, socket.NETLINK_ROUTE)
                self._socket.bind((os.getpid(), self.RTMGRP_LINK))
            except Exception as e:
                self._socket = None
                self._logger.info(f"Netlink bind failed: {e}")
                return False
            self._state = {}
            self._thread = threading.Thread(target=self.listen)
            self._thread.daemon = True
            self._thread.start()
            self._logger.info("Netlink started")
            return True

    def stop(self) -> bool:
        with self._condition:
            thread, self._thread = self._thread, None
            old_socket, self._socket = self._socket, None
        if bool(old_socket):
            self._logger.debug("Netlink socket shutdown")
            try:
                old_socket.shutdown(socket.SHUT_RDWR)
            except OSError as e:
                self._logger.debug(f"Netlink socket shutdown error: {e}")
            old_socket.close()
        if thread:
            self._logger.debug("Netlink join thread")
            thread.join()
            return True
        self._logger.info("Netlink not started")
        return False

    def listen(self) -> None:
        self._logger.info("Netlink listen start")
        while True:
            with self._condition:
                if not bool(self._socket):
                    break
                socket = self._socket
            try:
                data = socket.recv(65535)
                if data is None:
                    self._logger.info("Netlink no data")
                    break
            except Exception as e:
                self._logger.info(f"Netlink receive failed: {e}")
                break

            msg_len, msg_type, flags, seq, pid = struct.unpack("=LHHLL", data[:16])
            if msg_type == self.NLMSG_NOOP:
                continue
            if msg_type == self.NLMSG_ERROR:
                self._logger.info("Netlink error")
                break
            if msg_type not in (self.RTM_NEWLINK, self.RTM_DELLINK):
                continue

            data = data[16:]
            family, _, if_type, index, flags, change = struct.unpack("=BBHiII", data[:16])
            remaining = msg_len - 32
            data = data[16:]

            while remaining:
                rta_len, rta_type = struct.unpack("=HH", data[:4])
                if rta_len < 4:
                    break
                rta_data = data[4:rta_len]
                increment = (rta_len + 4 - 1) & ~(4 - 1)
                data = data[increment:]
                remaining -= increment
                if rta_type == self.IFLA_IFNAME:
                    name = rta_data.decode('utf8').rstrip('\x00')
                    up = bool(flags & 1)
                    known = self._state.get(name, None)
                    if up != known:
                        self._state[name] = up
                        cached = self._cmdaemon.add_interface_state({"name": name, "up": up})
                        self._logger.info(
                            f"Netlink, interface: {name}, up: {up}, cached: {cached}, message: {msg_type}"
                        )
                        if up:
                            self._cmdaemon.send_warning_event(f"interface {name} came up")
                        else:
                            self._cmdaemon.send_warning_event(f"interface {name} went down")

        self._logger.info("Netlink listen ended")
