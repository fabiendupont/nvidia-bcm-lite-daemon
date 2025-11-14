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


import os

from OpenSSL import crypto


class Private_Key:
    TYPE_RSA = crypto.TYPE_RSA
    TYPE_DSA = crypto.TYPE_DSA

    def __init__(self):
        self.pkey = None

    def generate(self, type=TYPE_RSA, bits=2048):
        self.pkey = crypto.PKey()
        self.pkey.generate_key(type, bits)
        return self.pkey

    def get_pem(self):
        return crypto.dump_privatekey(crypto.FILETYPE_PEM, self.pkey).decode("utf-8")

    def save(self, filename, mode=0o600):
        if self.pkey is None:
            return False
        pem = self.get_pem()
        with open(filename, "wt") as fd:
            os.chmod(filename, mode)
            fd.write(pem)
            return True
        return False
