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
import traceback
from uuid import UUID
from uuid import uuid4

from cm_lite_daemon.device.lldp import LLDP
from cm_lite_daemon.event_handler import Event_Handler
from cm_lite_daemon.object_to_json_encoder import Object_To_JSON_Encoder
from cm_lite_daemon.version import Version


class Request_Handler:
    def __init__(self, logger):
        self._logger = logger
        self._cmdaemon = None
        self._event_handler = Event_Handler(self._logger)
        self._version_info_uuid = str(uuid4())

    def set_cmdaemon(self, cmdaemon):
        self._cmdaemon = cmdaemon
        self._event_handler.set_cmdaemon(cmdaemon)

    def handle(self, uuid, data):
        if "errormessage" in data:
            self._logger.warning(f"Handle error: {data['errormessage']}")
            return False
        elif "service" not in data or "call" not in data:
            self._logger.warning("Received badly formatted request")
            self._logger.warning(data)
            return False
        service = data["service"]
        call = data["call"]
        caller = f"_{service}_{call}"
        self._logger.debug(f"Handle {caller}")
        try:
            caller = getattr(self, caller)
            return caller(uuid, data)
        except AttributeError as e:
            self._logger.info(f"Not implemented call: {caller} ({e}):\n{traceback.format_exc()}")
        except Exception as e:
            self._logger.info(f"Handle error: {e}:\n{traceback.format_exc()}")
        return self._undefined_service_call(uuid, data, caller)

    def _send(self, data):
        try:
            data = json.dumps(data, cls=Object_To_JSON_Encoder, ensure_ascii=True)
        except Exception as e:
            self._logger.warning(f"Failed to make send respose: {str(e)}")
            return False
        self._logger.debug(f"Send reply, size: {len(data)}")
        return self._cmdaemon._connection.send(data)

    def _undefined_service_call(self, uuid, data, caller):
        response = {"uuid": uuid, "errormessage": f"Not implemented: {caller}"}
        return self._send(response)

    def _cmmain_getVersion(self, uuid, data):
        response = {
            "uuid": uuid,
            "data": {
                "baseType": "VersionInfo",
                "uuid": self._version_info_uuid,
                "ref_node_uuid": self._cmdaemon.uuid,
                "cmdaemonVersion": "3.1",
                "cmdaemonBuildIndex": Version.revision,
                "cmdaemonBuildHash": Version.commit_id,
                "databaseVersion": 0,
            },
        }
        return self._send(response)

    def _cmdevice_lldp(self, uuid, data):
        response = {"uuid": uuid, "data": LLDP(self._cmdaemon, self._logger).connections}
        return self._send(response)

    def _cmdevice_reload(self, uuid, data):
        if self._cmdaemon is not None:
            reloaded = self._cmdaemon.reload()
        else:
            reloaded = False
        response = {"uuid": uuid, "data": reloaded}
        return self._send(response)

    def _cmdevice_reboot(self, uuid, data):
        if self._cmdaemon is not None:
            success = self._cmdaemon.reboot()
        else:
            success = False
        response = {"uuid": uuid, "data": {"success": success}}
        return self._send(response)

    def _cmdevice_shutdown(self, uuid, data):
        if self._cmdaemon is not None:
            success = self._cmdaemon.shutdown()
        else:
            success = False
        response = {"uuid": uuid, "data": {"success": success}}
        return self._send(response)

    def _cmdevice_getDhcpdLeases(self, uuid, data):
        if self._cmdaemon is not None:
            success, error, leases = self._cmdaemon.get_dhcpd_leases()
            result = {"success": success}
            if bool(error):
                result["error"] = error
            if bool(leases):
                result["leases"] = leases
        else:
            result = {"success": False, "error": "no cmdaemon"}
        response = {"uuid": uuid, "data": {"result": result}}
        return self._send(response)

    def _cmsession_handleEvents(self, uuid, data):
        if "events" in data:
            result = self._event_handler.handle(data["events"])
        else:
            self._logger.info("Handle events called without payload")
            result = False
        response = {"uuid": uuid, "data": result}
        return self._send(response)

    def _cmmon_monitoringDebug(self, uuid, data):
        if self._cmdaemon is not None:
            level = data.get("level", 0)
            changed = self._cmdaemon._monitoring_controller.debug(level)
            self._logger.info(f"Monitoring debug: {level}, changed: {changed}")
        response = {
            "uuid": uuid,
            "data": {"changed": changed},
        }
        return self._send(response)

    def _cmmon_fetchCachedData(self, uuid, data):
        cache_data = []
        prometheus_data = []
        if self._cmdaemon is not None:
            last_good = ("lastGood" in data) and data["lastGood"]
            cache_data = self._cmdaemon._monitoring_controller._cache.fetch(last_good)
        self._logger.debug(f"Fetch cached data, size ({len(cache_data)}, {len(prometheus_data)})")
        response = {
            "uuid": uuid,
            "data": {"cacheData": cache_data, "prometheusData": prometheus_data},
        }
        return self._send(response)

    def _cmmon_sample_now(self, uuid, data):
        result = False
        if self._cmdaemon is not None:
            tracker = data["tracker"]
            request = data["request"]
            result = self._cmdaemon._monitoring_controller.sample_now(tracker, request)
        response = {"uuid": uuid, "data": result}
        return self._send(response)

    def _cmmon_pushLiteMonitoredEntitiesAndMeasurables(self, uuid, data):
        processed = False
        if self._cmdaemon is not None:
            added_entities = data.get("added_entities", [])
            updated_entities = data.get("updated_entities", [])
            removed_entities = data.get("removed_entities", [])
            added_measurables = data.get("added_measurables", [])
            updated_measurables = data.get("updated_measurables", [])
            removed_measurables = data.get("removed_measurables", [])
            processed = self._cmdaemon._monitoring_controller.update_entities_measurables(
                added_entities,
                updated_entities,
                removed_entities,
                added_measurables,
                updated_measurables,
                removed_measurables,
            )
            self._logger.info(
                f"Pushed entities: ({len(added_entities)}, {len(updated_entities)}, {len(removed_entities)})"
                f", measurables: ({len(added_measurables)}, {len(updated_measurables)}, {len(removed_measurables)})"
            )
        else:
            self._logger.info("Pushed entities, measurables: no cmdaemon")
        response = {"uuid": uuid, "data": processed}
        return self._send(response)

    def _cmmon_reinitializeDataProducers(self, uuid, data):
        reinitialized = 0
        if self._cmdaemon is not None:
            producers = [UUID(it) for it in data.get("producers", [])]
            entities = [UUID(it) for it in data.get("entities", [])]
            reinitialized = self._cmdaemon._monitoring_controller._task_initializer.reinitialize(producers, entities)
            self._logger.debug(
                f"Reinitialize producers: {len(producers)}, entities: {len(entities)}, reinitialized: {reinitialized}"
            )
        response = {"uuid": uuid, "data": reinitialized}
        return self._send(response)

    def _cmdevice_getPortByMac(self, uuid, data):
        if self._cmdaemon is not None and self._cmdaemon._device is not None:
            detected_port, detected_breakout_port = self._cmdaemon._device.get_port_by_mac(data["mac"])
            if detected_port is not None:
                detected_switch = self._cmdaemon.uuid
            else:
                detected_switch = str(UUID(int=0))
                detected_port = 0
                detected_breakout_port = -1
        else:
            detected_switch = str(UUID(int=0))
            detected_port = 0
            detected_breakout_port = -1
        response = {
            "uuid": uuid,
            "data": {
                "switch_uuid": detected_switch,
                "port_number": detected_port,
                "breakout_port_number": detected_breakout_port,
            },
        }
        return self._send(response)

    def _cmdevice_updateSysInfoCollectors(self, uuid, data):
        if self._cmdaemon is not None:
            success = self._cmdaemon.push_sys_info_collector()
        else:
            success = False
        response = {"uuid": uuid, "data": success}
        return self._send(response)

    def _cmdevice_listDeviceCommands(self, uuid, data):
        if self._cmdaemon is not None and self._cmdaemon._device is not None:
            commands = self._cmdaemon._device.commands(data.get("force", False))
        else:
            commands = {}
        response = {"uuid": uuid, "data": {"commands": commands}}
        return self._send(response)

    def _cmdevice_showDeviceCommands(self, uuid, data):
        if self._cmdaemon is not None and self._cmdaemon._device is not None:
            exit_code, show, stderr = self._cmdaemon._device.show_commands()
        else:
            exit_code = -1
            show = None
            stderr = "Lite device not configured"
        response = {"uuid": uuid, "data": {"exit_code": exit_code, "show": show, "stderr": stderr}}
        return self._send(response)

    def _cmdevice_showDeviceCommandsYAML(self, uuid, data):
        if self._cmdaemon is not None and self._cmdaemon._device is not None:
            exit_code, show, stderr = self._cmdaemon._device.show_commands_yaml()
        else:
            exit_code = -1
            show = ""
            stderr = "Lite device not configured"
        response = {"uuid": uuid, "data": {"exit_code": exit_code, "yaml": show, "stderr": stderr}}
        return self._send(response)

    def _cmdevice_diffDeviceCommands(self, uuid, data):
        if self._cmdaemon is not None and self._cmdaemon._device is not None:
            exit_code, diff, stderr = self._cmdaemon._device.diff_commands()
        else:
            exit_code = -1
            diff = None
            stderr = "Lite device not configured"
        response = {"uuid": uuid, "data": {"exit_code": exit_code, "diff": diff, "stderr": stderr}}
        return self._send(response)

    def _cmdevice_saveDeviceCommands(self, uuid, data):
        if self._cmdaemon is not None and self._cmdaemon._device is not None:
            exit_code, stdout, stderr = self._cmdaemon._device.save_commands()
        else:
            exit_code = -1
            stdout = ""
            stderr = "Lite device not configured"
        response = {"uuid": uuid, "data": {"exit_code": exit_code, "stdout": stdout, "stderr": stderr}}
        return self._send(response)

    def _cmdevice_detachDeviceCommands(self, uuid, data):
        if self._cmdaemon is not None and self._cmdaemon._device is not None:
            exit_code, stdout, stderr = self._cmdaemon._device.detach_commands()
        else:
            exit_code = -1
            stdout = ""
            stderr = "Lite device not configured"
        response = {"uuid": uuid, "data": {"exit_code": exit_code, "stdout": stdout, "stderr": stderr}}
        return self._send(response)

    def _cmdevice_applyDeviceCommands(self, uuid, data):
        if self._cmdaemon is not None and self._cmdaemon._device is not None:
            exit_code, stdout, stderr = self._cmdaemon._device.apply_commands(
                data.get("staged", False), data.get("stage_only", False)
            )
        else:
            exit_code = -1
            stdout = ""
            stderr = "Lite device not configured"
        response = {"uuid": uuid, "data": {"exit_code": exit_code, "stdout": stdout, "stderr": stderr}}
        return self._send(response)

    def _cmdevice_syncLog(self, uuid, data):
        if self._cmdaemon is not None and self._cmdaemon._device is not None:
            lines = self._cmdaemon._device.sync_log(data.get("path", False))
        else:
            lines = "Lite device not configured"
        response = {"uuid": uuid, "data": lines}
        return self._send(response)

    def _cmgui_getSwitchOverview(self, uuid, data):
        if self._cmdaemon is not None and self._cmdaemon._device is not None:
            overview = self._cmdaemon._device.switch_overview
        else:
            overview = None
        response = {"uuid": uuid, "data": overview}
        return self._send(response)

    def _cmserv_getOSServices(self, uuid, data):
        if self._cmdaemon is not None:
            services = self._cmdaemon.get_os_services()
        else:
            services = []
        response = {"uuid": uuid, "data": services}
        return self._send(response)

    def _cmserv_getOSService(self, uuid, data):
        if self._cmdaemon is not None:
            services = self._cmdaemon.get_os_service(data.get("name", None))
        else:
            services = None
        response = {"uuid": uuid, "data": services}
        return self._send(response)

    def _cmserv_startOSService(self, uuid, data):
        if self._cmdaemon is not None:
            success = self._cmdaemon.start_os_service(data.get("name", None), data.get("args", []))
        else:
            success = False
        response = {"uuid": uuid, "data": success}
        return self._send(response)

    def _cmserv_restartOSService(self, uuid, data):
        if self._cmdaemon is not None:
            success = self._cmdaemon.restart_os_service(data.get("name", None), data.get("args", []))
        else:
            success = False
        response = {"uuid": uuid, "data": success}
        return self._send(response)

    def _cmserv_stopOSService(self, uuid, data):
        if self._cmdaemon is not None:
            success = self._cmdaemon.stop_os_service(data.get("name", None), data.get("args", []))
        else:
            success = False
        response = {"uuid": uuid, "data": success}
        return self._send(response)

    def _cmserv_reloadOSService(self, uuid, data):
        if self._cmdaemon is not None:
            success = self._cmdaemon.reload_os_service(data.get("name", None), data.get("args", []))
        else:
            success = False
        response = {"uuid": uuid, "data": success}
        return self._send(response)

    def _cmserv_resetOSService(self, uuid, data):
        if self._cmdaemon is not None:
            success = self._cmdaemon.reset_os_service(data.get("name", None), data.get("args", []))
        else:
            success = False
        response = {"uuid": uuid, "data": success}
        return self._send(response)

    def _cmserv_callInitScript(self, uuid, data):
        if self._cmdaemon is not None:
            success = self._cmdaemon.call_os_service_init_script(
                data.get("name", None), data.get("action", None), data.get("args", [])
            )
        else:
            success = False
        response = {"uuid": uuid, "data": success}
        return self._send(response)

    def _cmdevice_getPtmTopology(self, uuid, data):
        if self._cmdaemon is not None and self._cmdaemon._device is not None:
            exit_code, stdout, stderr = self._cmdaemon._device.get_ptm_topology()
        else:
            exit_code = -1
            stdout = ""
            stderr = "Lite device not configured"
        response = {"uuid": uuid, "data": {"exit_code": exit_code, "stdout": stdout, "stderr": stderr}}
        return self._send(response)

    def _cmdevice_applyPtmTopology(self, uuid, data):
        if self._cmdaemon is not None and self._cmdaemon._device is not None:
            exit_code, stdout, stderr = self._cmdaemon._device.apply_ptm_topology(data.get("data", None))
        else:
            exit_code = -1
            stdout = ""
            stderr = "Lite device not configured"
        response = {"uuid": uuid, "data": {"exit_code": exit_code, "stdout": stdout, "stderr": stderr}}
        return self._send(response)

    def _cmdevice_factoryReset(self, uuid, data):
        if self._cmdaemon is not None and self._cmdaemon._device is not None:
            result = self._cmdaemon._device.factory_reset(data.get("force", False))
        else:
            result = {"success": False, "message": "Device not initialized"}
        response = {"uuid": uuid, "data": result}
        return self._send(response)

    def _cmdevice_showSystemZtp(self, uuid, data):
        if self._cmdaemon is not None and self._cmdaemon._device is not None:
            result = self._cmdaemon._device.show_system_ztp()
        else:
            result = {"success": False, "message": "Device not initialized"}
        response = {"uuid": uuid, "data": result}
        return self._send(response)

    def _cmdevice_showSdnPartition(self, uuid, data):
        if self._cmdaemon is not None and self._cmdaemon._device is not None:
            result = self._cmdaemon._device.show_sdn_partition()
        else:
            result = {"success": False, "message": "Device not initialized"}
        response = {"uuid": uuid, "data": result}
        return self._send(response)

    def _cmdevice_nvfabricStart(self, uuid, data):
        if self._cmdaemon is not None and self._cmdaemon._device is not None:
            result = self._cmdaemon._device.nvfabric_start()
        else:
            result = {"success": False, "message": "Device not initialized"}
        response = {"uuid": uuid, "data": result}
        return self._send(response)

    def _cmdevice_nvfabricStop(self, uuid, data):
        if self._cmdaemon is not None and self._cmdaemon._device is not None:
            result = self._cmdaemon._device.nvfabric_stop()
        else:
            result = {"success": False, "message": "Device not initialized"}
        response = {"uuid": uuid, "data": result}
        return self._send(response)

    def _cmdevice_nvfabricStatus(self, uuid, data):
        if self._cmdaemon is not None and self._cmdaemon._device is not None:
            result = self._cmdaemon._device.nvfabric_status()
        else:
            result = {"success": False, "message": "Device not initialized"}
        response = {"uuid": uuid, "data": result}
        return self._send(response)

    def _cmdevice_nvfabricHealth(self, uuid, data):
        if self._cmdaemon is not None and self._cmdaemon._device is not None:
            result = self._cmdaemon._device.nvfabric_health()
        else:
            result = {"success": False, "message": "Device not initialized"}
        response = {"uuid": uuid, "data": result}
        return self._send(response)

    def _cmdevice_nvfabricShowAction(self, uuid, data):
        if self._cmdaemon is not None and self._cmdaemon._device is not None:
            result = self._cmdaemon._device.nvfabric_show_action()
        else:
            result = {"success": False, "message": "Device not initialized"}
        response = {"uuid": uuid, "data": result}
        return self._send(response)
