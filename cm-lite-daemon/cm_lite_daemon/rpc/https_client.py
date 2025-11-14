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


import http.client
import urllib.error
import urllib.parse
import urllib.request


class HTTPSClientAuthHandler(urllib.request.HTTPSHandler):
    def __init__(self, settings):
        urllib.request.HTTPSHandler.__init__(self)
        self.settings = settings

    def https_open(self, req):
        return self.do_open(self.getConnection, req)

    def getConnection(self, host, timeout=120):
        return http.client.HTTPSConnection(host, context=self.settings.context, timeout=timeout)
