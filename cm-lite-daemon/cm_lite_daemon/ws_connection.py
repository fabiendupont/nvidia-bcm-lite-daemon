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

import random
import sys
import threading

import websocket

from cm_lite_daemon.request_handler import Request_Handler
from cm_lite_daemon.rpc.ws_request import WS_Request
from cm_lite_daemon.ws_request_cache import WS_Request_Cache


class WS_Connection:
    def __init__(self, settings, logger):
        self._settings = settings
        self._logger = logger
        self._cmdaemon = None
        self._ws = None
        self._thread = None
        self._message_threads = []
        self._version = None
        self._open = False
        self._send_condition = threading.Condition()
        self._starting_condition = None
        self._request_handler = Request_Handler(self._logger)
        self._request_cache = WS_Request_Cache(self._request_handler, self._logger)
        self._get_mask_key = None
        if self._settings.websocket_masked:
            self._get_mask_key = self._mask_generator

    def _mask_generator(self, n):
        return bytearray(random.getrandbits(8) for _ in range(n))

    def __reset_ws(self):
        self._logger.info(f"Reset, active threads, {len(self._message_threads)}")
        for thread in self._message_threads:
            thread.join()
        self._message_threads = []
        self._ws = websocket.WebSocketApp(
            self.__url(),
            get_mask_key=self._get_mask_key,
            on_open=self._on_open,
            on_message=self._on_message,
            on_ping=self._on_ping,
            on_pong=self._on_pong,
            on_error=self._on_error,
            on_close=self._on_close,
        )

    def set_cmdaemon(self, cmdaemon):
        self._cmdaemon = cmdaemon
        self._request_cache.set_cmdaemon(cmdaemon)
        self._request_handler.set_cmdaemon(cmdaemon)

    def __url(self):
        if self._settings.is_ssl():
            return f"wss://{self._settings.host}:{int(self._settings.port)}/ws"
        else:
            return f"ws://{self._settings.host}:{int(self._settings.port)}/ws"

    def get_version(self):
        request = WS_Request(self)
        request.call("main", "getVersion")
        self._version = request.wait()
        return self._version

    def run(self, trace=None, timeout=10):
        if self._open:
            return True
        if trace is not None:
            websocket.enableTrace(trace)
        self._logger.info(f"Websocket trace: {trace}")
        args = {"ping_interval": 600, "ping_timeout": 30}
        if self._settings.is_ssl():
            args["sslopt"] = {
                "cert_reqs": self._settings.context.verify_mode,
                "ca_cert": self._settings.ca_file,
                "ca_certs": self._settings.ca_file,
                "certfile": self._settings.cert_file,
                "keyfile": self._settings.key_file,
                "check_hostname": self._settings.context.check_hostname,
            }
        self.__reset_ws()
        self._ws.last_ping_tm = 0
        self._ws.last_pong_tm = 0
        self._thread = threading.Thread(target=self._ws.run_forever, kwargs=args)
        self._thread.daemon = True
        self._thread.start()
        self._starting_condition = threading.Condition()
        self._starting_condition.acquire()
        self._open = False
        self._starting_condition.wait(timeout)
        self._starting_condition.release()
        self._starting_condition = None
        return self._open

    def send(self, data):
        try:
            self._logger.debug(f"Write, {len(data)} bytes")
            return self._ws.send(data)
        except websocket._exceptions.WebSocketConnectionClosedException:
            self._open = False
            self._logger.info("WebSocket stopped, send failed")
        return 0

    def stop(self):
        was_open, self._open = self._open, False
        try:
            self._ws.close()
            self._logger.debug("WebSocket closed")
        except websocket._exceptions.WebSocketConnectionClosedException:
            self.ws.keep_running = False
            self._logger.debug("WebSocket failed to close")
        if self._thread is not None and was_open:
            # KDR: bug in websocket, doesn't join if the socket never opened
            self._logger.debug("WebSocket join thread")
            self._thread.join()
        self._thread = None
        self._logger.debug("WebSocket stopped")

    def _on_message(self, *data):
        try:
            message = data[-1]
            self._logger.debug(f"Message, {len(message)} bytes")
            old_threads = len(self._message_threads)
            for thread in self._message_threads:
                thread.join(timeout=0)
            self._message_threads = [thread for thread in self._message_threads if thread.is_alive()]
            thread = threading.Thread(target=self._request_cache.data, args=(message,))
            self._message_threads.append(thread)
            self._logger.debug(f"Active threads: {len(self._message_threads)}, before: {old_threads}")
            thread.daemon = True
            thread.start()
        except Exception:
            if self._cmdaemon is None:
                self._logger.info(f"Error: {sys.exc_info()}")
            else:
                self._cmdaemon.report_error(sys.exc_info())

    def _on_error(self, *data):
        error = data[-1]
        if self._starting_condition is not None:
            self._logger.warning(error)
            self._starting_condition.acquire()
            self._open = False
            self._starting_condition.notify()
            self._starting_condition.release()
        elif self._cmdaemon is not None:
            self._open = self._cmdaemon.communication_error(error)
        else:
            self._open = False
        self._logger.info(f"WebSocket error, open: {self._open}")

    def _on_close(self, *data):
        self._open = False
        self._logger.info("WebSocket closed")
        if self._cmdaemon is not None:
            self._open = self._cmdaemon.communication_error()

    def _on_open(self, *data):
        if self._starting_condition is None:
            self._logger.warning("WebSocket open took too long")
        else:
            self._starting_condition.acquire()
            self._open = True
            self._starting_condition.notify()
            self._starting_condition.release()

    def _on_ping(self, *data):
        self._logger.debug("recieved ping")

    def _on_pong(self, *data):
        self._logger.debug("recieved pong")
