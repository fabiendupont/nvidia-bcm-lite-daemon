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


class ExitCodes:
    OK = 0
    REGISTER_SESSION = 1
    ZERO_SESSION = 2
    REQUEST_CERTIFICATE = 3
    NO_CERTIFICATE = 4
    SAVE_FAILED = 5
    RPC_ERROR = 6
    INSTALL_FAILED = 7
    PYTHON_VERSION = 9
    HTTP_CONNECTION = 10
    WS_CONNECTION = 11
    NOT_FOUND = 12
    COMMAND_FAILED = 13
