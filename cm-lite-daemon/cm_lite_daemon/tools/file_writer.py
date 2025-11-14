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


def file_writer(source, destination, replace=None, bound="@", mode=None):
    try:
        with open(source, "rt") as fin:
            lines = fin.readlines()
        with open(destination, "wt") as fout:
            for line in lines:
                if replace is not None:
                    for k, v in replace.items():
                        line = line.replace(f"{bound}{k}{bound}", v)
                fout.write(line)
        if mode is not None:
            os.chmod(destination, mode)
        return True
    except Exception:
        return False
