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


import json
import os
import socket
import ssl

from cm_lite_daemon.object_to_json_encoder import Object_To_JSON_Encoder
from cm_lite_daemon.util import is_valid_ipv4_address


class Settings:
    def __init__(
        self,
        host="master",
        port=8081,
        cert_file=None,
        key_file=None,
        bootstrap_cert_file=None,
        bootstrap_key_file=None,
        ca_file=None,
        node=None,
        websocket_masked=False,
        check_hostname=True,
        follow_redirect=True,
        cert_check=True,
        force_ssl=False,
    ):
        self.host = host
        self.active = None
        self.passive = None
        self.shared = None
        self.port = port
        self.cert_file = cert_file
        self.key_file = key_file
        self.bootstrap_cert_file = bootstrap_cert_file
        self.bootstrap_key_file = bootstrap_key_file
        self.ca_file = ca_file
        self.websocket_masked = websocket_masked
        self.follow_redirect = follow_redirect
        self.context = None
        self.force_ssl = force_ssl
        self.cert_check = cert_check
        self.check_hostname = check_hostname

        if node is None:
            self.node = socket.gethostname().split(".", 1)[0]
        else:
            self.node = node

        if self.host is not None:
            self.__load_ssl()

    def __load_ssl(self):
        self.context = ssl.create_default_context(cafile=self.ca_file)
        self.context.check_hostname = self.check_hostname and not is_valid_ipv4_address(self.host)
        if self.cert_check or self.context.check_hostname:
            self.context.verify_mode = ssl.CERT_REQUIRED
        else:
            self.context.verify_mode = ssl.CERT_NONE

        if self.cert_file is not None and os.path.exists(self.cert_file) and os.path.exists(self.key_file):
            self.context.load_cert_chain(self.cert_file, self.key_file)
        elif (
            self.bootstrap_cert_file is not None
            and os.path.exists(self.bootstrap_cert_file)
            and os.path.exists(self.bootstrap_key_file)
        ):
            self.context.load_cert_chain(self.bootstrap_cert_file, self.bootstrap_key_file)

    def reload_certificate(self):
        if self.cert_file is not None:
            context = ssl.create_default_context(cafile=self.ca_file)
            context.check_hostname = self.context.check_hostname and not is_valid_ipv4_address(self.host)
            context.verify_mode = self.context.verify_mode
            if os.path.exists(self.cert_file) and os.path.exists(self.key_file):
                context.load_cert_chain(self.cert_file, self.key_file)
            self.context = context

    def is_ssl(self):
        return self.force_ssl or self.cert_file is not None or self.ca_file is not None

    def check_certificate_files(self):
        return os.path.exists(self.cert_file) and os.path.exists(self.key_file)

    def save(self, filename=None, mode=0o600):
        data = {
            field: getattr(self, field)
            for field in (
                "host",
                "active",
                "passive",
                "shared",
                "port",
                "ca_file",
                "cert_file",
                "key_file",
                "node",
                "check_hostname",
                "websocket_masked",
                "follow_redirect",
                "force_ssl",
                "cert_check",
            )
        }
        if filename is None:
            filename = self.filename
        with open(filename, "w") as f:
            os.chmod(filename, mode)
            f.write(json.dumps(data, cls=Object_To_JSON_Encoder, ensure_ascii=True))
            return True
        return False

    def load(self, filename):
        try:
            with open(filename, "r") as f:
                data = json.loads(f.read())
                for k, v in data.items():
                    setattr(self, k, v)
                self.__load_ssl()
                self.filename = filename
                return True
        except Exception:
            pass
        return False
