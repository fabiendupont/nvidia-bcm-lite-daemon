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

from OpenSSL import crypto


class CSR:
    def __init__(self, key):
        self.csr = None
        self.key = key

    def generate(self, digest="sha256", common_name=None, domains=None):
        if common_name is None:
            common_name = socket.gethostname().split(".", 1)[0]
        self.csr = crypto.X509Req()
        self.csr.get_subject().CN = common_name
        if domains is not None:
            domains = ", ".join(f"DNS:{d}" for d in domains)
            self.csr.add_extensions(
                [
                    crypto.X509Extension("subjectAltName", critical=False, value=domains),
                ]
            )
        self.csr.set_pubkey(self.key.pkey)
        self.csr.sign(self.key.pkey, digest)
        return self.csr

    def get_pem(self):
        return crypto.dump_certificate_request(crypto.FILETYPE_PEM, self.csr).decode("utf-8")
