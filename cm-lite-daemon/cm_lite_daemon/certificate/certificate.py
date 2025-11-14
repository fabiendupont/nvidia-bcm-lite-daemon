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


class Certificate:
    def __init__(self, pem):
        self.pem = pem
        self.certificate = crypto.load_certificate(crypto.FILETYPE_PEM, self.pem)

    def valid(self):
        return self.certificate is not None

    def info(self):
        print(f"Subject: {self.certificate.get_subject().get_components()}")
        print(f"Issuer:  {self.certificate.get_issuer().get_components()}")
        print(("Serial:  %d" % self.certificate.get_serial_number()))
        print(f"Expire:  {self.certificate.get_notAfter()}")

    def save(self, filename, mode=0o600):
        with open(filename, "wt") as fd:
            os.chmod(filename, mode)
            fd.write(self.pem)
            return True
        return False
