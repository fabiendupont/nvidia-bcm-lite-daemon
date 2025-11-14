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

import json
import os
import queue
import re
import subprocess
import threading
import time
import traceback
from uuid import UUID
from uuid import uuid4

from cm_lite_daemon.device.cumulus import Cumulus
from cm_lite_daemon.device.fake import Fake
from cm_lite_daemon.device.fake_switch import FakeSwitch
from cm_lite_daemon.device.nvlink_switch import NVLinkSwitch
from cm_lite_daemon.device.service import Service
from cm_lite_daemon.fifo_cache import FIFOCache
from cm_lite_daemon.gnss_location_scraper import GNSSLocationScraper
from cm_lite_daemon.monitoring.controller import Controller
from cm_lite_daemon.monitoring.sampler.scheduler import Scheduler
from cm_lite_daemon.rpc.ws_request import WS_Request
from cm_lite_daemon.script import Script
from cm_lite_daemon.sys_info_collector import Sys_Info_Collector
from cm_lite_daemon.util import contains
from cm_lite_daemon.util import get_mac
from cm_lite_daemon.util import next_period


class CMDaemon:
    device_update_file = "/var/run/cm-lite-daemon.apply"

    CLIENT_TYPE_LITENODE = 7

    def __init__(self, settings, connection, logger, root_directory: str | None = None):
        self._settings = settings
        self._connection = connection
        self._connection.set_cmdaemon(self)
        self._hostname = settings.node
        self._session_uuid = None
        self._lite_node = None
        self._resources = []
        self._partition = None
        self._status = None
        self._logger = logger
        self._scheduler = Scheduler()
        self._error_queue = queue.Queue()
        self._gnss_location_scraper = GNSSLocationScraper(self, self._logger, self._connection)
        self._monitoring_controller = Controller(self, self._logger, self._scheduler, self._connection)
        self._running = False
        self._reconnect = False
        self._condition = threading.Condition()
        self._sys_info = Sys_Info_Collector()
        self._sys_info_dirty = False
        self._head_node_ips = None
        self._environment = None
        self._device = None
        self._frozen_files = None
        self.services = []
        if root_directory is None:
            self.root_directory = os.path.dirname(os.path.abspath(os.path.dirname(__file__)))
            self._uuid_path = None
        else:
            self.root_directory = root_directory
            self._uuid_path = f"{self.root_directory}/etc/uuid"
        self._do_maintenance_count = 0
        self._trace = os.path.exists('/root/.websocket.trace')
        self._venv_free_environment = None
        self._interface_state_fifo_cache = FIFOCache()
        self.fake = None
        self._logger.info(f"Cache uuid path: {self._uuid_path}")

    def write_uuid(self) -> None:
        if bool(self._lite_node) and bool(self._uuid_path):
            with open(self._uuid_path, "w") as fd:
                fd.write(self._lite_node["uuid"])
            self._logger.info(f"Updated: {self._uuid_path}")

    def read_uuid(self) -> str | None:
        if bool(self._uuid_path):
            if os.path.exists(self._uuid_path):
                with open(self._uuid_path) as fd:
                    return fd.readline().strip()
            self._logger.debug(f"Unable to find: {self._uuid_path}")
        return None

    def find_node(self):
        lite_node = None

        if uuid := self.read_uuid():
            self._logger.info(f"Find node {uuid}")
            request = WS_Request(self._connection)
            request.call("device", "getLiteDevice", [uuid])
            lite_node = request.wait(timeout=50)
            if lite_node is None:
                self._logger.warning(f"Unable to find configuration for {uuid}")

        if lite_node is None:
            self._logger.info(f"Find node {self._hostname}")
            request = WS_Request(self._connection)
            request.call("device", "getLiteDevice", [self._hostname])
            lite_node = request.wait(timeout=50)
            if lite_node is None:
                self._logger.warning(f"Unable to find configuration for {self._hostname}")

        if lite_node is None:
            if mac := get_mac("eth0"):
                self._logger.info(f"Find node via {mac}")
                request = WS_Request(self._connection)
                request.call("device", "getLiteDevice", [mac])
                lite_node = request.wait(timeout=50)
                if lite_node is None:
                    self._logger.warning(f"Unable to find configuration for {mac}")

        if lite_node is None:
            return False

        self._lite_node = lite_node
        self.write_uuid()

        self._logger.debug("Get resources")
        request = WS_Request(self._connection)
        request.call("mon", "getEntityResources", [lite_node["uuid"]])
        resources = request.wait(timeout=15)
        if isinstance(resources, list):
            self._resources = resources
            self._logger.info(f"Monitoring resources: {', '.join(self._resources)}")
        else:
            self._logger.info(f"Unknown resources: {resources}")

        self._logger.debug("Get partition")
        request = WS_Request(self._connection)
        request.call("part", "getPartition", [self._lite_node["partition"]])
        partition = request.wait(timeout=50)
        if partition is None:
            self._logger.warning(f"Unable to find partition for {self._hostname}")
            return False
        self._partition = partition

        self.fake = Fake(self._logger, self._lite_node['hostname'])
        if not bool(self._device):
            child_type = self._lite_node.get("childType", "")
            if child_type.endswith("Switch"):
                # TODO: CM-41202 support for other devices
                if self._lite_node.get("revision", "") == "fake":
                    self._device = FakeSwitch(self, self._logger)
                    self._logger.info("Set up fake switch")
                elif self._lite_node.get("kind", "") == "NVLINK":
                    self._device = NVLinkSwitch(self, self._logger)
                    self._logger.info("Set up NVLink switch")
                else:
                    self._device = Cumulus(self, self._logger)
                    self._logger.info("Set up Cumulus switch")
            else:
                self._logger.info(f"Do not set up a special device for {child_type}")
        elif isinstance(self._device, Cumulus):
            self._device._ztp_checked = True
        self.update_environment()
        self.update_services()
        self._logger.info(
            f"Found my own configuration for {self._lite_node['hostname']}"
            f"({self._lite_node['mac']} / {self._lite_node['uuid']})"
        )
        return True

    def get_head_node_ips(self, try_active_passive=True):
        if not self._settings.follow_redirect:
            self._logger.info("Not following head node IP redirect")
            return True
        request = WS_Request(self._connection)
        request.call("main", "getHeadNodeIPs")
        self._head_node_ips = request.wait()
        if self._head_node_ips is None:
            host = self._settings.host
            self._logger.warning(f"Unable to get head node IPs via {host}")
            if try_active_passive:
                checked = {host}
                for it in (self._settings.active, self._settings.passive, self._settings.shared):
                    if bool(it) and it not in checked:
                        self._settings.host = it
                        if self.get_head_node_ips(False):
                            self._logger.warning(f"Switch host {host} to {it}")
                            return True
                        checked.add(it)
            self._settings.host = host
            return False
        self.update_environment()
        if self._head_node_ips["passive_head_node_ip"] == "":
            self._logger.info(f"Retrieved single head node IP: {self._head_node_ips['active_head_node_ip']}")
        else:
            self._logger.info(
                f"Retrieved head node IPs active: {self._head_node_ips['active_head_node_ip']}, "
                f"passive: {self._head_node_ips['passive_head_node_ip']}, "
                f"shared: {self._head_node_ips['shared_head_node_ip']}, "
                f"update in {self._settings.filename}"
            )
            self._settings.active = self._head_node_ips['active_head_node_ip']
            self._settings.passive = self._head_node_ips['passive_head_node_ip']
            self._settings.shared = self._head_node_ips['shared_head_node_ip']
            self._settings.save()
        return True

    def initialize(self):
        self._logger.debug("Initialize")
        return self._monitoring_controller.initialize()

    @property
    def uuid(self) -> UUID:
        if bool(self._lite_node):
            return UUID(self._lite_node.get("uuid"))
        return UUID(int=0)

    @property
    def hostname(self) -> str:
        if bool(self._lite_node):
            return self._lite_node.get("hostname", self._hostname)
        return self._hostname

    @property
    def snmp_settings(self) -> dict | None:
        snmp_settings = self._lite_node.get("snmpSettings", None)
        if snmp_settings is None:
            snmp_settings = self._partition.get("snmpSettings", None)
        return snmp_settings

    @property
    def access_settings(self) -> dict | None:
        access_settings = self._lite_node.get("accessSettings", None)
        if access_settings is None:
            access_settings = self._partition.get("accessSettings", None)
        return access_settings

    @property
    def ztp_settings(self) -> dict | None:
        ztp_settings = self._lite_node.get("ztpSettings", None)
        if ztp_settings is None:
            ztp_settings = self._partition.get("ztpSettings", None)
        return ztp_settings

    @property
    def timezone_settings(self) -> dict | None:
        time_zone_settings = self._lite_node.get("timeZoneSettings", None)
        if time_zone_settings is None:
            time_zone_settings = self._partition.get("timeZoneSettings", None)
        return time_zone_settings

    @property
    def ntp_servers(self) -> list[str]:
        return ["master"] + self._partition.get("timeServers", [])

    @property
    def _lite_node_services(self) -> list[dict]:
        services = self._lite_node.get("services", [])
        self._logger.debug(f"Defined services: {len(services)}")
        return services

    def failed_services(self) -> list[str]:
        return [it.name for it in self.services if it.failing]

    def call_os_service_init_script(self, name: str | None, action: str | None, args: list[str]) -> int:
        service = next((it for it in self.services if it.name == name), None)
        if bool(service):
            return service.call(action, args)
        return -100

    def start_os_service(self, name: str | None, args: list[str]) -> int:
        service = next((it for it in self.services if it.name == name), None)
        if bool(service):
            return service.start(args)
        return -100

    def restart_os_service(self, name: str | None, args: list[str]) -> int:
        service = next((it for it in self.services if it.name == name), None)
        if bool(service):
            return service.restart(args)
        return -100

    def stop_os_service(self, name: str | None, args: list[str]) -> int:
        service = next((it for it in self.services if it.name == name), None)
        if bool(service):
            return service.stop(args)
        return -100

    def reload_os_service(self, name: str | None, args: list[str]) -> int:
        service = next((it for it in self.services if it.name == name), None)
        if bool(service):
            return service.reload(args)
        return -100

    def reset_os_service(self, name: str | None, args: list[str]) -> int:
        service = next((it for it in self.services if it.name == name), None)
        if bool(service):
            return service.reset(args)
        return -100

    def get_os_service(self, name: str | None) -> dict | None:
        service = next((it for it in self.services if it.name == name), None)
        if bool(service):
            return service.info()
        return None

    def get_os_services(self) -> list[dict]:
        return [it.info() for it in self.services]

    def update_services(self) -> None:
        desired_services = [
            it for it in [Service(self, self._logger, jt) for jt in self._lite_node_services] if it.valid
        ]
        new_services = []
        keep_services = []
        for service in desired_services:
            find = next((it for it in self.services if it.name == service.name), None)
            if find is None:
                self._logger.info(f"Add new service:{service.name}")
                new_services.append(service)
                service.check()
            else:
                find.data = service.data
        for service in self.services:
            find = next((it for it in desired_services if it.name == service.name), None)
            if find is None:
                self._logger.info(f"Remove service: {service.name}")
            else:
                self._logger.debug(f"Keep service:{service.name}")
                keep_services.append(service)
        self.services = keep_services + new_services
        self._logger.info(f"Updated services, configured: {len(self.services)}")

    def get_ip(self) -> str:
        best_ip = "127.0.0.1"
        best_priority = -1
        for it in self._lite_node.get("interfaces", []):
            ip = it.get("ip", "0.0.0.0")
            if ip != "0.0.0.0":
                priority = it.get("onNetworkPriority", 0)
                if priority > best_priority:
                    best_priority = priority
                    best_ip = ip
        return best_ip

    def update_environment(self) -> bool:
        if self._lite_node is None:
            return False
        self._environment = {
            "CMD_HOSTNAME": self._lite_node["hostname"],
            "CMD_IP": self.get_ip(),
            "CMD_MAC": self._lite_node["mac"],
            "CMD_USERDEFINED1": self._lite_node["userdefined1"],
            "CMD_USERDEFINED2": self._lite_node["userdefined2"],
            "CMD_DEVICE_TYPE": "LiteNode",
            "CMD_STATUS": "UP",
        }
        if kind := self._lite_node.get("kind", None):
            self._environment["CMD_KIND"] = kind.upper()
        if self._head_node_ips is not None:
            self._environment["CMD_ACTIVE_HEAD_NODE_IP"] = self._head_node_ips["active_head_node_ip"]
        snmp_settings = self.snmp_settings
        if bool(snmp_settings):
            self._environment["CMD_READ_STRING"] = snmp_settings["readString"]
        extra_values = self._lite_node.get("extra_values", None)
        if isinstance(extra_values, dict):
            for key, value in extra_values.items():
                if key.startswith("CMD_"):
                    self._environment[key] = value
        self._venv_free_environment = None
        return True

    def register(self) -> None | UUID:
        if self._lite_node is None:
            return None
        self.unregister()
        request = WS_Request(self._connection)
        request.call("session", "registerLiteNodeSession", [self.uuid])
        self._session_uuid = request.wait()
        if self._session_uuid is None:
            self._logger.warning(f"Failed to register session: {request.error()}")
            return None
        self._logger.info(f"Registered session: {self._session_uuid} for node: {self.uuid}")
        return self._session_uuid

    def unregister(self) -> bool:
        if self._lite_node is None or self._session_uuid is None:
            return False
        request = WS_Request(self._connection)
        request.call("session", "endNodeSession", [self.uuid])
        unregistered = request.wait()
        if unregistered:
            self._logger.info(f"End node session: {self._session_uuid} node: {self.uuid}")
        else:
            self._logger.warning(f"Failed to end session: {self._session_uuid}, error: {request.error()}")
        self._session_uuid = None
        return unregistered

    def push_sys_info_collector(self) -> bool:
        if self._lite_node is None:
            return False
        self._sys_info.ref_device_uuid = self.uuid
        self._sys_info.detect()
        if self._device is not None:
            self._sys_info.extra = self._device.sys_info()
        request = WS_Request(self._connection)
        request.call("device", "putSysInfoCollector", [self._sys_info])
        updated = request.wait()
        if updated:
            self._logger.info("Pushed system information")
        else:
            self._logger.warning(f"Failed to push system information: {request.error()}")
        return updated

    def remote_update_status(self, device_uuid: UUID, status: str) -> bool:
        if self.uuid == device_uuid:
            self._status = status
            self._logger.debug(f"Updated status to {status['status']}")
        return True

    def set_up(self, message: str | None = None):
        if self._lite_node is None:
            return False

        request = WS_Request(self._connection)
        request.call(
            "status",
            "setUp",
            [
                self.uuid,
                "" if message is None else message,
                False if message is None else True,
            ],
        )
        if request.wait():
            self._logger.info("Updating status to UP")
        else:
            self._logger.warning("Failed to update status")
        return self._status

    def set_down(self, message: str | None = None):
        if self._lite_node is None:
            return False

        request = WS_Request(self._connection)
        request.call(
            "status",
            "setDown",
            [
                self.uuid,
                "" if message is None else message,
                False if message is None else True,
            ],
        )
        if request.wait():
            self._logger.info("Updating status to DOWN")
        else:
            self._logger.warning("Failed to update status")
        return self._status

    def get_status(self) -> dict:
        request = WS_Request(self._connection)
        request.call("device", "getStatus", [self.uuid])
        self._status = request.wait()
        if self._status is None:
            self._logger.warning("Unable to fetch status")
        else:
            self._logger.info(f"Current status {self._status['status']}")
        return self._status

    def reload(self):
        self._logger.debug("CMDaemon reloading")
        result = self.find_node() and self.initialize()
        self._logger.info(f"CMDaemon reloaded, result: {result}")
        return result

    def _start(self):
        self._logger.info("CMDaemon starting")
        if self.get_head_node_ips() and self.find_node() and self.register() and self.initialize():
            self.set_up(message="")
            self._logger.info("CMDaemon started")
            return True
        self._logger.warning("CMDaemon failed to start")
        return False

    def _wait_os_ready(self, timeout: float = 360, delay: float = 30):
        if os.path.exists("/root/.fake.switch"):
            self._logger.info("Do not wait for nv cli to become available (cod)")
            return True
        for path in ("/usr/sbin", "/usr/bin", "/sbin", "/bin"):
            nv = f"{path}/nv"
            if os.path.exists(nv):
                start = time.monotonic()
                self._logger.info(f"Wait for {nv} cli to become available")
                while True:
                    process = subprocess.run(
                        [nv, "show", "system"],
                        env=self.venv_free_environment,
                        capture_output=True,
                        text=True,
                    )
                    if process.returncode == 0:
                        if "NVOS CLI is unavailable" not in process.stdout:
                            break
                    self._logger.info(f"nv show system: {process.stdout}")
                    if start + timeout < time.monotonic():
                        return False
                    time.sleep(delay)
                break
        return True

    def start(self):
        if not self._wait_os_ready():
            self._logger.warning("Timed out waiting for OS to be ready")
        if self._start():
            self.run()
            self.set_down()
        self.unregister()

    def stop(self):
        self._logger.info("CMDaemon stopping")
        self._condition.acquire()
        self._running = False
        self._condition.notify()
        self._condition.release()
        self._monitoring_controller.stop()
        self._gnss_location_scraper.stop()
        self._logger.debug("CMDaemon stop issued")

    def _run(self):
        reconnect_counter = 0
        if bool(self._device) and os.path.exists(self.device_update_file):
            self._logger.debug("CMDaemon apply commands on first start")
            self._device.apply_commands()
            os.remove(self.device_update_file)
        self._condition.acquire()
        self._do_maintenance_count = 0
        self._logger.debug("CMDaemon running")
        self._condition.wait(15)
        while self._running:
            try:
                error = self._error_queue.get(block=False)
            except queue.Empty:
                pass
            else:
                exc_type, exc_obj, exc_trace = error
                e_traceback = traceback.format_exception(exc_type, exc_obj, exc_trace)
                traceback_lines = []
                for line in [line.rstrip("\n") for line in e_traceback]:
                    traceback_lines.extend(line.splitlines())
                for line in traceback_lines:
                    self._logger.warning(line)
            if self._reconnect:
                reconnect_counter += 1
                self._logger.info(f"CMDaemon reconnecting, count: {reconnect_counter}")
                if reconnect_counter <= 0:
                    self._condition.wait(60)
                else:
                    self._condition.wait(15)
                self._condition.release()
                try:
                    if self._connection.run(trace=self._trace):
                        if self._start() and self._connection._open:
                            self._logger.info(f"CMDaemon reconnected, attempts: {reconnect_counter}")
                            self._reconnect = False
                            reconnect_counter = 0
                        else:
                            self._logger.info(f"CMDaemon reconnected failed(start): {reconnect_counter}")
                    else:
                        self._logger.info(f"CMDaemon reconnection failed(run): {reconnect_counter}")
                except Exception as e:
                    self._logger.info(f"CMDaemon reconnection error: {e}")
                self._condition.acquire()
            else:
                self.do_maintenance()
                self._condition.wait(60)
        self._logger.debug("CMDaemon done running")
        self._condition.release()
        if self._device:
            self._device.stop()

    def do_maintenance(self):
        self._do_maintenance_count += 1
        self._logger.debug(f"CMDaemon maintenance, count {self._do_maintenance_count}")
        self._monitoring_controller.do_maintenance()
        for service in self.services:
            service.check()
        if self._device:
            self._device.do_maintenance()
        now = int(time.time())
        if next_period(now, 60, 3600) or self._do_maintenance_count <= 10:
            self.set_up()
        if next_period(now, 60, 86400) or self._do_maintenance_count <= 1 or self._sys_info_dirty:
            self._sys_info_dirty = False
            self.push_sys_info_collector()

    def wakeup(self):
        self._condition.acquire()
        self._condition.notify()
        self._condition.release()

    def report_error(self, error):
        self._condition.acquire()
        self._error_queue.put(error)
        self._condition.notify()
        self._condition.release()

    def run(self):
        if self._running:
            return False
        self._logger.info("CMDaemon Lite running")
        self._monitoring_controller.start()
        self._gnss_location_scraper.start()
        self._running = True
        self._run()
        self._logger.info("CMDaemon Lite no longer running")
        return True

    def end_session(self, reason):
        self._logger.info(f"End session: {reason}")
        self._reconnect = True
        self._logger.debug("End session, start reconnect")
        self.wakeup()

    def communication_error(self, error=None):
        was_reconnect = self._reconnect
        if self._running:
            if error is not None:
                self._logger.info(f"Connection lost: {str(error)}")
            self._reconnect = True
        if not was_reconnect:
            self.wakeup()

    @property
    def venv_free_environment(self) -> dict[str, str]:
        if self._venv_free_environment is None:
            self._venv_free_environment = os.environ.copy()
            if bool(self._environment):
                self._venv_free_environment.update(self._environment)
            if "HOME" not in self._venv_free_environment:
                self._venv_free_environment["HOME"] = "/root"
            if "VIRTUAL_ENV" in self._venv_free_environment:
                self._venv_free_environment["PATH"] = ':'.join(
                    it
                    for it in self._venv_free_environment.get("PATH").split(':')
                    if not it.startswith(self._venv_free_environment["VIRTUAL_ENV"])
                )
                del self._venv_free_environment["VIRTUAL_ENV"]
            self._venv_free_environment["PATH"] = ':'.join(
                it for it in self._venv_free_environment.get("PATH").split(':') if not it.startswith("/cm/")
            )
            self._logger.info(f'Path: {self._venv_free_environment["PATH"]}')
        return self._venv_free_environment

    def _load_frozen_files(self) -> None:
        frozen_file_path = f"{self.run_directory}/etc/frozen_files.json"
        if os.path.exists(frozen_file_path):
            with open(frozen_file_path, "r") as fd:
                self._frozen_files = {
                    re.compile(filename) if filename[0] == '^' else filename: frozen
                    for filename, frozen in json.load(fd).items()
                }
            self._logger.info(f"Load frozen file: {frozen_file_path}, items: {len(self._frozen_files)}")

    def is_frozen(self, path: str) -> bool:
        if not bool(self._frozen_files):
            return False
        frozen = self._frozen_files.get(path, None)
        if frozen is None:
            for regex, config in self._frozen_files.items():
                if not isinstance(regex, str):
                    if regex.match(path):
                        frozen = config
                        break
        if frozen is None:
            return False
        if isinstance(frozen, bool):
            return frozen
        if isinstance(frozen, list):
            return self._lite_node["hostname"] in frozen
        if isinstance(frozen, dict):
            return frozen.get(self._lite_node["hostname"], False)
        return False

    def report_file_write(self, path: str, frozen: bool = False) -> None:
        info = {
            "ref_device_uuid": self._lite_node["uuid"],
            "path": path,
            "actor": "CM_LITE_DAEMON",
            "timestamp": int(time.time()),
            "frozen": frozen,
        }
        request = WS_Request(self._connection)
        request.call("cmdevice", "addFileWriteInfo", [info])

    def reboot(self) -> bool:
        self._logger.info("reboot")
        if bool(self._device):
            result = self._device.reboot()
            if result is not None:
                return result
        return os.system("/sbin/shutdown -r --no-wall +0") == 0

    def shutdown(self) -> bool:
        self._logger.info("shutdown")
        if bool(self._device):
            result = self._device.shutdown()
            if result is not None:
                return result
        return os.system("/sbin/shutdown -h --no-wall +0") == 0

    def add_interface_state(self, interface_state) -> int:
        return self._interface_state_fifo_cache.add(interface_state)

    def get_interface_states(self) -> list:
        return self._interface_state_fifo_cache.get(timed=True, delete=True)

    def _send_event(self, event: dict) -> None:
        self._logger.debug(f"Send event: {event.get('childType')}")
        event["uuid"] = str(uuid4())
        event["creation_time"] = int(time.time())
        event["source_device"] = str(self.uuid)
        request = WS_Request(self._connection)
        request.call("session", "handleEvent", [event])

    def send_warning_event(self, message: str, extended_message: str = "") -> None:
        return self._send_event(
            {
                "baseType": "Event",
                "childType": "WarningEvent",
                "broadcast": True,
                "msg": message,
                "extendedMsg": extended_message,
            }
        )

    def send_service_event(self, service: str, operation: str, result: bool, info: str = "") -> None:
        return self._send_event(
            {
                "baseType": "Event",
                "childType": "ServiceEvent",
                "broadcast": True,
                "service": service,
                "operation": operation,
                "result": result,
                "info": info,
            }
        )

    def get_dhcpd_leases(self) -> tuple[bool, str | None, list[dict[str, str | int]] | None]:
        args = ["/cm/local/apps/cm-lite-daemon/scripts/cm-dhcpd-leases-parse.py"]
        success, script = Script(self._logger).run(args, 10, False)
        data = None
        error = None
        if success:
            try:
                data = json.loads(data)
            except Exception as e:
                success = False
                error = str(e)
        return success, error, data

    def has_resource(self, resource: str, exact: bool = False) -> bool:
        if not exact and (len(resource) > 2) and (resource[0] == "/") and (resource[-1] == "/"):
            matcher = re.compile(resource[1:-1], re.I)
            return bool(sum(0 if matcher.match(it) is None else 1 for it in self._resources))
        return contains(self._resources, resource)
