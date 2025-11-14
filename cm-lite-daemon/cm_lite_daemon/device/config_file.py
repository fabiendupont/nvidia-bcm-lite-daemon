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

from __future__ import annotations

import os
import re
from datetime import datetime


class ConfigFile:
    header = "# Written by cm-lite-daemon"

    def __init__(self, cmdaemon, path: str, backup: bool = True):
        self._path = path
        self._cmdaemon = cmdaemon
        self._backup = backup

    def _read_old_content(self) -> tuple[bool, str]:
        if os.path.exists(self._path):
            with open(self._path, "r") as fd:
                old_content = fd.read()
            return True, old_content
        return False, ""

    def _create_containing_directory(self) -> bool:
        directory = os.path.dirname(self._path)
        os.makedirs(directory, exist_ok=True)
        return os.path.exists(directory)

    def _create_backup(self, content: str):
        now = datetime.now()  # current date and time
        date_time = now.strftime("%m-%d-%Y-%H-%M-%S")
        backup_path = f"{self._path}.{date_time}"
        with open(backup_path, "w") as fd:
            fd.write(content)

    def write_whole_file(self, content: str, write_missing: bool = True) -> bool:
        found, old_content = self._read_old_content()
        if (not found and not write_missing) or (old_content == content):
            return False
        frozen = self._cmdaemon.is_frozen(self._path)
        if not frozen:
            if self._create_containing_directory():
                if found and self._backup:
                    self._create_backup(old_content)
                with open(self._path, "w") as fd:
                    fd.write(f"{self.header}\n")
                    fd.write(content)
            else:
                return False
        self._cmdaemon.report_file_write(self._path, frozen)
        return True

    def replace_lines_matching(self, find: str, replace: list[str], write_missing: bool = False) -> bool:
        found, old_content = self._read_old_content()
        if not found and not write_missing:
            return False
        old_lines = [it.strip() for it in old_content.split("\n") if not it.startswith(self.header) if bool(it)]
        new_lines = [self.header]
        find_regex = re.compile(find)
        for line in old_lines:
            if bool(find_regex.match(line)):
                if bool(replace):
                    new_lines += replace
                    replace = []
            else:
                new_lines.append(line)
        if bool(replace):
            new_lines += replace
        if new_lines == old_lines:
            return False
        frozen = self._cmdaemon.is_frozen(self._path)
        if not frozen:
            if self._create_containing_directory():
                if found and self._backup:
                    self._create_backup(old_content)
                with open(self._path, "w") as fd:
                    fd.writelines(f"{it}\n" for it in new_lines)
            else:
                return False
        self._cmdaemon.report_file_write(self._path, frozen)
        return True
