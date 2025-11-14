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


class HTTP_Connection:
    CLIENT_TYPE_LITENODE = 7
    CLIENT_TYPE_LITE_INSTALLER = 8

    def __init__(self, settings, logger):
        self.settings = settings
        self.logger = logger
        self.session_uuid = None
        self.version = None

    def get_version(self):
        self.version = None
        rpc = RPC(self.settings)
        (code, out) = rpc.call(service="main", call="getVersion")
        if code == 0:
            self.version = out
        else:
            self.logger.warning(f"Unable to get version: ({int(code)}) {out}")
        return self.version

    def register_session(self):
        self.session_uuid = None
        rpc = RPC(self.settings)
        (code, out) = rpc.call(
            service="session",
            call="registerSession",
            args=[self.CLIENT_TYPE_LITE_INSTALLER],
        )
        if code != 0:
            self.logger.warning(f"Unable to register session: ({int(code)}) {out}")
        elif out == 0:
            self.logger.warning(f"Zero session: ({int(code)}) {out}")
        else:
            self.session_uuid = out
        return self.session_uuid

    def unregister_session(self):
        if self.session_uuid is None:
            return False
        rpc = RPC(self.settings)
        (code, out) = rpc.call(service="session", call="unregisterSession", args=[self.session_uuid])
        if code != 0:
            self.logger.warning(f"Unable to unregister session: ({int(code)}) {out}")
        elif not out:
            self.logger.warning(f"Failed to unregister session: ({int(code)}) {out}")
        else:
            self.logger.debug(f"Unregister session: {self.session_uuid}")
            self.session_uuid = None
        return self.session_uuid is None

    def wait_for_event(self, types=None):
        rpc = RPC(self.settings)
        while self.session_uuid is not None:
            (code, out) = rpc.call(service="session", call="waitForEvents", args=[self.session_uuid, 30])
            if code != 0:
                self.logger.warning(f"Wait for events failed: ({int(code)}) {out}")
                break
            for event in out:
                if types is None or (event["childType"] in types):
                    return event
        return None
