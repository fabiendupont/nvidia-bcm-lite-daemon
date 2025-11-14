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
import urllib.error
import urllib.parse
import urllib.request

from cm_lite_daemon.object_to_json_encoder import Object_To_JSON_Encoder
from cm_lite_daemon.rpc.https_client import HTTPSClientAuthHandler


class RPC:
    OK = 0
    JSON_ERROR = -98
    URL_ERROR = -99
    GENERIC_ERROR = -100

    def __init__(self, settings):
        self.settings = settings
        self.opener = urllib.request.build_opener(HTTPSClientAuthHandler(self.settings))

    def call(self, service, call, args=None, timeout=None):
        data = {"service": service, "call": call, "args": [] if args is None else args}
        return self._call(data, timeout)

    def __url(self):
        if self.settings.is_ssl():
            return f"https://{self.settings.host}:{int(self.settings.port)}/json"
        else:
            return f"http://{self.settings.host}:{int(self.settings.port)}/json"

    def _call(self, data, timeout=None):
        try:
            jsondata = json.dumps(data, cls=Object_To_JSON_Encoder).encode("ascii")
            request = urllib.request.Request(self.__url(), jsondata)
            request.add_header("Content-Type", "application/json")
            response = self.opener.open(request)
            data = response.read().decode("utf-8")
            return self.OK, json.loads(data)
        except ValueError as e:
            return self.JSON_ERROR, str(e)
        except urllib.error.HTTPError as e:
            return e.code, e.reason
        except urllib.error.URLError as e:
            return self.URL_ERROR, e.reason
        except Exception as e:
            return self.GENERIC_ERROR, str(e)
