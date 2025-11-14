#
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
# KDR: one big file for now, likely lots of changes coming: easier to refactor in one go
#

from __future__ import annotations

import json
import os
import re
import subprocess
import threading
from enum import Enum
from enum import auto
from time import time

from cm_lite_daemon.rpc.ws_request import WS_Request


class Serialize:
    def serialize(self) -> dict[str, str | int | list[str]]:
        return {
            key: value if isinstance(value, (str, int, list)) else value.name for key, value in self.__dict__.items()
        }


class Argument(Serialize):
    class Type(Enum):
        TEXT = auto()
        RANGE = auto()
        FIELD = auto()
        REGEX = auto()
        OPTIONS = auto()

    re_field = re.compile(r"^<(.*)>$")
    re_range = re.compile(r"^(\d+)\-(\d+)$")
    re_regex = re.compile(r"^\((.*)\)$")

    def __init__(self, word: str):
        if match := self.re_field.match(word):
            self.field = match[1]
            self.type = self.Type.FIELD
        elif match := self.re_regex.match(word):
            if "-" in match[1]:
                self.regex = match[1]
                self.type = self.Type.REGEX
            else:
                # TODO: fields inside options
                self.options = match[1].split("|")
                self.type = self.Type.OPTIONS
        elif match := self.re_range.match(word):
            self.minimum = int(match[1])
            self.maximum = int(match[2])
            self.type = self.Type.RANGE
        else:
            self.word = word
            self.type = self.Type.TEXT


class Command(Serialize):
    def __init__(self, line: str):
        self.arguments = [Argument(it) for it in line.split(" ")]

    def serialize(self) -> list[dict[str, str | int]]:
        return [it.serialize() for it in self.arguments]

    @property
    def fields(self) -> list[str]:
        # TODO from options
        return [it.field for it in self.arguments if it.type == Argument.Type.FIELD]


class Field(Serialize):
    class Type(Enum):
        REGEX = auto()
        CREATE = auto()
        OPTIONS = auto()
        REGEX_OPTIONS = auto()

    def __init__(self, name: str, type: Type):
        self.name = name
        self.type = type


class RegexField(Field):
    def __init__(self, name: str, regex: str):
        super().__init__(name, self.Type.REGEX)
        self.regex = regex


class RegexOptionsField(Field):
    def __init__(self, name: str, regex: str = ""):
        super().__init__(name, self.Type.REGEX_OPTIONS)
        self.regex = regex
        self.options = []


class InterfaceIdField(RegexOptionsField):
    def __init__(self, env: dict[str, str] | None = None):
        super().__init__("interface-id")
        if os.path.exists("/root/.fake.cumulus"):
            self.options = [f"swp{i}" for i in range(1, 17)]
            self.options.append("eth0")
        elif os.path.exists("/usr/sbin/ip"):
            process = subprocess.run(["/usr/sbin/ip", "-j", "address"], capture_output=True, text=True, env=env)
            if bool(process.returncode):
                raise RuntimeError(process.stderr)
            try:
                self.options = [it.get("ifname", None) for it in json.loads(process.stdout)]
            except json.decoder.JSONDecodeError:
                self.options = []
        else:
            self.options = []
        other_options = '|'.join(it for it in self.options if not it.startswith("swp"))
        self.regex = rf"^(swp\d+([,\-]\d+)*|{other_options})$"


class VrfNameField(RegexOptionsField):
    def __init__(self, env: dict[str, str] | None = None, name: str = "vrf-name"):
        super().__init__(name, r"^\w+$")
        if os.path.exists("/root/.fake.cumulus"):
            self.options = ["mgmt"]
        elif os.path.exists("/usr/sbin/ip"):
            process = subprocess.run(["/usr/sbin/ip", "-j", "vrf"], capture_output=True, text=True, env=env)
            if bool(process.returncode):
                raise RuntimeError(process.stderr)
            try:
                self.options = [it.get("name", None) for it in json.loads(process.stdout)]
            except json.decoder.JSONDecodeError:
                self.options = []
        else:
            self.options = []


class VrfIdField(RegexOptionsField):
    def __init__(self, env: dict[str, str] | None = None):
        super().__init__("vrf-id", r"^\d+$")
        if os.path.exists("/root/.fake.cumulus"):
            self.options = [1001]
        elif os.path.exists("/usr/sbin/ip"):
            process = subprocess.run(["/usr/sbin/ip", "-j", "vrf"], capture_output=True, text=True, env=env)
            if bool(process.returncode):
                raise RuntimeError(process.stderr)
            try:
                self.options = [it.get("table", None) for it in json.loads(process.stdout)]
            except json.decoder.JSONDecodeError:
                self.options = []
        else:
            self.options = []


class NV:
    def __init__(self, cmdaemon, logger):
        self._cmdaemon = cmdaemon
        self._logger = logger
        self.commands = []
        self.fields = [
            RegexField("value", r"^.+$"),
            RegexField("readonly-community-id", r"^[^\s]{4,16}$"),
            RegexField("ip-prefix-id", r"^((25[0-5]|(2[0-4]|1\d|[1-9]|)\d)\.?\b){4}(/\d+)?$"),
            RegexField("ip-gateway-id", r"^((25[0-5]|(2[0-4]|1\d|[1-9]|)\d)\.?\b){4}(/\d+)?$"),
            RegexField("listening-address-id", r"^((25[0-5]|(2[0-4]|1\d|[1-9]|)\d)\.?\b){4}|all|all-v6$"),
            RegexField("ignore-id", r"^(/[^/ ]*)+/?$"),
            RegexField("idn-hostname", r"(?!^[0-9]+$)^([a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9-]*[a-zA-Z0-9])$"),
            RegexField("ipv4", r"^((25[0-5]|(2[0-4]|1\d|[1-9]|)\d)\.?\b){4}$"),
            RegexField("server-id", r"^((25[0-5]|(2[0-4]|1\d|[1-9]|)\d)\.?\b){4}$"),  # or hostname?
            RegexField("dns-server-id", r"^((25[0-5]|(2[0-4]|1\d|[1-9]|)\d)\.?\b){4}$"),
            # VrfIdField(self._cmdaemon.venv_free_environment),  # KDR: doesn't work with ID
            VrfNameField(self._cmdaemon.venv_free_environment, "vrf-id"),
            VrfNameField(self._cmdaemon.venv_free_environment, "vrf-name"),
            InterfaceIdField(self._cmdaemon.venv_free_environment),
        ]
        self.error = None
        self.loading = False
        self.timestamp = 0
        self._thread = None
        self._condition = threading.Condition()
        if bool(self._cmdaemon.fake.nv):
            self.nv = self._cmdaemon.fake.nv
        else:
            self.nv = "nv"
            for path in ("/usr/sbin", "/usr/bin", "/sbin", "/bin"):
                self.nv = f"{path}/nv"
                if os.path.exists(self.nv):
                    break

    def load_async(self) -> bool:
        with self._condition:
            if self.loading:
                self._logger.info("NV load async already busy")
                return False
            if bool(self._thread):
                self._logger.debug("NV load async, join old thread")
                self._thread.join()
            self._logger.info("NV load async, starting thread")
            self.loading = True
            self._thread = threading.Thread(target=self.load)
            self._thread.daemon = True
            self._thread.start()
            return True

    def load(self) -> None:
        """
        This can take > 60s
        """
        try:
            process = subprocess.run(
                [self.nv, "list-commands"],
                env=self._cmdaemon.venv_free_environment,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            process = None

        with self._condition:
            self.loading = False
            self.timestamp = int(time())
            if not bool(process):
                self._logger.info("NV load error: command not found")
                self.error = "no nv"
                self.commands = []
            elif bool(process.returncode):
                self._logger.info(f"NV load error: {process.stderr}")
                self.error = process.stderr
                self.commands = []
            else:
                try:
                    self.commands = [Command(it) for it in process.stdout.split("\n") if bool(it)]
                    self.error = None
                    self._logger.info(f"NV load commands: {len(self.commands)}")
                except RuntimeError as e:
                    self.error = str(e)
                    self.commands = []
                    self._logger.info(f"NV load error: {self.error}")
            self._condition.notify_all()

    def wait(self) -> None:
        with self._condition:
            while self.loading:
                self._condition.wait()

    def serialize(self) -> dict[str, str | int | bool | dict[str, bool] | list[dict[str, str | int | list[str]]]]:
        with self._condition:
            field_names = set(it.name for it in self.fields)
            return {
                "error": self.error,
                "loading": self.loading,
                "timestamp": self.timestamp,
                "fields": [it.serialize() for it in self.fields],
                "commands": [it.serialize() for it in self.commands],
                "status": {jt: jt in field_names for it in self.commands for jt in it.fields},
            }

    def _convert(self, nv: list[dict]) -> list[list[str]]:
        def iterate(data, stack: list[str]) -> list[list[str]]:
            result = []
            for key, value in data.items():
                if isinstance(value, dict):
                    result += iterate(value, stack + [key])
                else:
                    result.append(stack + [key, value])
            return result

        result = []
        for name in ["set", "unset"]:
            nv_set = next((it for it in nv if name in it), None)
            result += iterate(nv_set, []) if bool(nv_set) else []
        return result

    def diff(self) -> tuple[int, list[dict] | None, str]:
        self._logger.info("NV diff")
        process = subprocess.run(
            [self.nv, "--output", "json", "config", "diff"],
            env=self._cmdaemon.venv_free_environment,
            capture_output=True,
            text=True,
        )
        diff = None
        error = process.stderr
        if not bool(process.returncode):
            try:
                diff = self._convert(json.loads(process.stdout))
            except Exception as e:
                error = str(e)
                self._logger.info(f"NV diff error: {error}")
        return process.returncode, diff, error

    def show(self) -> tuple[int, list[dict] | None, str]:
        self._logger.info("NV show")
        process = subprocess.run(
            [self.nv, "--output", "json", "config", "show"],
            env=self._cmdaemon.venv_free_environment,
            capture_output=True,
            text=True,
        )
        show = None
        error = process.stderr
        if not bool(process.returncode):
            try:
                show = self._convert(json.loads(process.stdout))
            except Exception as e:
                error = str(e)
                self._logger.info(f"NV show error: {error}")
        return process.returncode, show, error

    def show_yaml(self) -> tuple[int, str, str]:
        self._logger.info("NV show yaml")
        process = subprocess.run(
            [self.nv, "--output", "yaml", "config", "show"],
            env=self._cmdaemon.venv_free_environment,
            capture_output=True,
            text=True,
        )
        return process.returncode, str(process.stdout), str(process.stderr)

    def _get_auto_file_commands(self) -> tuple[dict | None, dict | None, str]:
        self._logger.info("Get auto/file commands")
        request = WS_Request(self._cmdaemon._connection)
        request.call("device", "getDeviceCommands", [self._cmdaemon.uuid])
        result = request.wait()
        if bool(result):
            return result.get("auto_commands", None), result.get("file_commands", None), result.get("file_path", "")
        self._logger.info("Failed to get auto/file commands")
        return None, None, ""

    def _stage_commands(self, commands: list[list[str]] | None) -> tuple[int, str, str]:
        if not bool(commands):
            return 0, "", ""
        self._logger.info(f"NV run {self.nv} unset (to mimic config replace)")
        process = subprocess.run(
            [self.nv, "unset"],
            env=self._cmdaemon.venv_free_environment,
            capture_output=True,
            text=True,
        )
        if bool(process.returncode):
            return process.returncode, process.stdout, process.stderr
        for command in commands:
            self._logger.info(f"NV run {self.nv} {command[1:]}")
            process = subprocess.run(
                [self.nv] + command[1:],
                env=self._cmdaemon.venv_free_environment,
                capture_output=True,
                text=True,
            )
            if bool(process.returncode):
                return process.returncode, process.stdout, process.stderr
        return 0, "", ""

    def apply(self, staged: bool = False, stage_only: bool = False) -> tuple[int, str, str]:
        mode = self._cmdaemon._lite_node.get("cumulusMode", "")
        if not staged:
            self._logger.info(f"NV apply, mode: {mode}, stage only: {stage_only}")
            if mode in ["AUTO", "FILE"]:
                auto_commands, file_commands, file_path = self._get_auto_file_commands()
            if mode == "AUTO":
                exit_code, stdout, stderr = self._stage_commands(auto_commands)
            else:
                exit_code = 0
            if mode in ["AUTO", "MANUAL"] and not bool(exit_code):
                exit_code, stdout, stderr = self._stage_commands(
                    self._cmdaemon._lite_node.get("cumulusConfiguration", None)
                )
            elif mode == "FILE":
                if bool(file_path):
                    exit_code, stdout, stderr = self._stage_commands(file_commands)
                else:
                    exit_code = -2
                    stdout = ""
                    stderr = "No file based commands defined"
            if bool(exit_code):
                return exit_code, stdout, stderr
            if stage_only:
                return 0, "staged", ""
            if os.path.exists("/cm/disable.nv.apply"):
                return 0, "disabled", ""
        elif stage_only:
            return 0, "nothing staged", ""
        args = [self.nv, "--output", "json"]
        if not stage_only:
            args += ["--assume-yes"]
        args += ["config", "apply"]
        process = subprocess.run(args, env=self._cmdaemon.venv_free_environment, capture_output=True, text=True)
        return process.returncode, process.stdout, process.stderr

    def detach(self) -> tuple[int, str, str]:
        self._logger.info("NV detach")
        process = subprocess.run(
            [self.nv, "config", "detach"],
            env=self._cmdaemon.venv_free_environment,
            capture_output=True,
            text=True,
        )
        return process.returncode, process.stdout, process.stderr

    def save(self) -> tuple[int, str, str]:
        self._logger.info("NV save")
        process = subprocess.run(
            [self.nv, "config", "save"],
            env=self._cmdaemon.venv_free_environment,
            capture_output=True,
            text=True,
        )
        return process.returncode, process.stdout, process.stderr

    def vrf(self) -> dict[str, str | int] | None:
        self._logger.info("NV vrf")
        process = subprocess.run(
            [self.nv, "--output", "json", "show", "vrf"],
            env=self._cmdaemon.venv_free_environment,
            capture_output=True,
            text=True,
        )
        if process.returncode:
            self._logger.info(process.stderr)
            return None

        def address(data: dict) -> str:
            if loopback := data.get("loopback", None):
                if ip := loopback.get("ip", None):
                    if address := ip.get("address", None):
                        return ", ".join(address.keys())
            return ""

        def router(data: dict) -> str:
            if router := data.get("router", None):
                return ", ".join(router.keys())
            return ""

        return [
            [
                {"name": "Name", "value": name},
                {"name": "Table", "value": data.get("table", 0)},
                {"name": "Address", "value": address(data)},
                {"name": "Router", "value": router(data)},
            ]
            for name, data in json.loads(process.stdout).items()
        ]
