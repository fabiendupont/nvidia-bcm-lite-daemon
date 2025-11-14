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
import typing

from cm_lite_daemon.monitoring.parser.value import Value
from cm_lite_daemon.monitoring.sampler.internal_sampler_task import Internal_Sampler_Task

if typing.TYPE_CHECKING:
    from uuid import UUID


class Network_IO_Sampler_Task(Internal_Sampler_Task):
    interface_state = "InterfaceState"
    interface_state_total = 3
    interface_state_totals = (("down", 0), ("up", 1), ("unknown", 2), ("total", interface_state_total))
    physical_states = [
        "NoStateChange",
        "Sleep",
        "Polling",
        "Disabled",
        "PortConfigurationTraining",
        "LinkUp",
        "LinkErrorRecovery",
        "PhyTest",
        "Unknown",  # last!
    ]

    def __init__(self, cmdaemon, interval: int, offset: int = 0, producer: UUID | None = None, excludeIf=None):
        super().__init__(interval=interval, offset=offset, producer=producer)
        self._cmdaemon = cmdaemon
        if bool(excludeIf):
            self.excludeIf = [it for it in excludeIf if bool(it) and it[0] != '/' and it[-1] != '*']
            self.excludeIfStart = [it[0:-1] for it in excludeIf if bool(it) and it[0] != '/' and it[-1] == '*']
            self.excludeIfRegex = [
                re.compile(it[1:-1]) for it in excludeIf if bool(it) and it[0] == '/' and it[-1] == '/'
            ]
        else:
            self.excludeIf = []
            self.excludeIfStart = []
            self.excludeIfRegex = []
        self.up_states = {"up"}
        if os.path.exists("/root/.fake.cumulus"):
            self.up_states.add("unknown")
        self._network_io_info = (
            ("BytesRecv", "bytes_recv", "Bytes received per second", "B/s"),
            ("PacketsRecv", "packets_recv", "Packets per second", "/s"),
            ("ErrorsRecv", "errin", "Received errors per second", "/s"),
            ("DropRecv", "dropin", "Received packets dropped per second", "/s"),
            ("BytesSent", "bytes_sent", "Bytes sent per second", "B/s"),
            ("PacketsSent", "packets_sent", "Packets per second", "/s"),
            ("ErrorsSent", "errout", "Sent errors per second", "/s"),
            ("DropSent", "dropout", "Sent packets droppped per second", "/s"),
        )

    def _io_counters(self):
        try:
            # TODO : is there a better way?
            from psutil import net_io_counters

            return net_io_counters(pernic=True)
        except ImportError:
            return None

    def __valid_value(self, text: str) -> bool:
        try:
            float(text)
            return True
        except (ValueError, TypeError):
            return False

    def _parse_nvue_interface_extra(
        self, interface: str, system: str, data: dict, now, entity
    ) -> list[dict[str, float | str | None]]:
        result = []
        if bool(data):
            result += [
                {
                    "producer": self.producer,
                    "entity": entity.name,
                    "timestamp": now,
                    "measurable": f"nv_interface_{name.replace('-', '_')}",
                    "parameter": interface,
                    "description": f"The value of {name}",
                    "type": f"NV/Interface/{system}",
                    "raw": float(value),
                    "rate": float(value),
                }
                for name, value in data.items()
                if self.__valid_value(value)
            ]
        return result

    def __nvue_name(self, name: str) -> str:
        name = name.replace('-', '_')
        name = name.removesuffix('_bits')
        name = name.removesuffix('_bytes')
        name = name.removesuffix('_percent')
        return f"nv_interface_{name}"

    def __nvue_unit(self, name: str) -> str:
        if name.endswith("bits"):
            return "b"
        if name.endswith("bytes"):
            return "B"
        if name.endswith("percent"):
            return "%"
        return ""

    def _parse_nvue_interface(self, interface: str, data: dict, now, entity) -> list[dict[str, float | str | None]]:
        result = []
        if link := data.get("link", None):
            if counters := link.get("counters", None):
                result += [
                    {
                        "producer": self.producer,
                        "entity": entity.name,
                        "timestamp": now,
                        "measurable": self.__nvue_name(name),
                        "parameter": interface,
                        "description": f"The value of {name}",
                        "type": "NV/Interface",
                        "cumulative": name.endswith("bytes"),
                        "unit": self.__nvue_unit(name),
                        "raw": value,
                        "rate": value,
                    }
                    for name, value in counters.items()
                ]
            if speed := link.get("speed", None):
                value = self._cmdaemon._device._speed_to_mb_per_second(speed)
                result += [
                    {
                        "producer": self.producer,
                        "entity": entity.name,
                        "timestamp": now,
                        "measurable": "nv_interface_speed",
                        "parameter": interface,
                        "description": "The speed of interface",
                        "type": "NV/Interface",
                        "unit": "b/s",
                        "raw": value,
                        "rate": value,
                    }
                ]
            if state := link.get("physical-state", None):
                try:
                    value = self.physical_states.index(state)
                    info = ""
                except ValueError:
                    value = len(self.physical_states) - 1  # Unknown
                    info = f"/* {state} */"
                result += [
                    {
                        "producer": self.producer,
                        "entity": entity.name,
                        "timestamp": now,
                        "measurable": "nv_physical_state",
                        "parameter": interface,
                        "description": "The physical state of the interface",
                        "type": "NV/Interface",
                        "info": info,
                        "range": {
                            "type": "Enum",
                            "values": [
                                {"key": index, "value": name} for index, name in enumerate(self.physical_states)
                            ],
                        },
                        "raw": value,
                        "rate": value,
                    }
                ]
            result += self._parse_nvue_interface_extra(interface, "Diag", link.get("phy-diag", None), now, entity)
            result += self._parse_nvue_interface_extra(interface, "Detail", link.get("phy-detail", None), now, entity)
        return result

    def _nvue_interfaces(self, now, entity) -> list[dict[str, float | str | None]] | None:
        if self._cmdaemon is None:
            return None
        if self._cmdaemon._device is None:
            return None
        interfaces = self._cmdaemon._device.nvue_interfaces()
        if not bool(interfaces):
            return None
        return sum(
            [
                self._parse_nvue_interface(name, item, now, entity)
                for name, item in interfaces.items()
                if name.startswith("acp") or name.startswith("fnm")
            ],
            [],
        )

    def _exclude(self, interface) -> bool:
        return (
            interface in self.excludeIf
            or any(interface.startswith(it) for it in self.excludeIfStart)
            or any(it.match(interface) for it in self.excludeIfRegex)
        )

    def initialize(self, now, entity, pool=None, asynchronous=True, follow_up=None):
        definitions = []
        io_counters = self._io_counters()
        if io_counters:
            swp_ports = set()
            for interface, io in io_counters.items():
                if self._exclude(interface):
                    continue
                definitions.append(
                    {
                        "producer": self.producer,
                        "measurable": self.interface_state,
                        "parameter": interface,
                        "entity": entity.name,
                        "type": "Network",
                        "cumulative": False,
                        "range": {
                            "type": "Enum",
                            "values": [
                                {"key": 0, "value": "down"},
                                {"key": 1, "value": "up"},
                                {"key": 2, "value": "unknown"},
                            ],
                        },
                        "description": "Interface operation state",
                    }
                )
                for name, item, description, unit in self._network_io_info:
                    if hasattr(io, item):
                        if interface.startswith("swp"):
                            swp_ports.add(interface)
                        definitions.append(
                            {
                                "producer": self.producer,
                                "measurable": name,
                                "parameter": interface,
                                "entity": entity.name,
                                "type": "Network",
                                "cumulative": True,
                                "unit": unit,
                                "description": description,
                            }
                        )
            if bool(swp_ports):
                if bool(self._cmdaemon) and bool(self._cmdaemon._device) and bool(self._cmdaemon._device.port_speeds):
                    for name in swp_ports:
                        definitions.append(
                            {
                                "producer": self.producer,
                                "measurable": "ReportedSpeed",
                                "parameter": name,
                                "entity": entity.name,
                                "type": "Network",
                                "cumulative": False,
                                "unit": "b/s",
                                "description": "Reported speed by the hardware",
                            }
                        )
                for name, _, description, unit in self._network_io_info:
                    definitions.append(
                        {
                            "producer": self.producer,
                            "measurable": name,
                            "parameter": "total",
                            "entity": entity.name,
                            "type": "Network",
                            "cumulative": True,
                            "unit": unit,
                            "description": description,
                        }
                    )
                for state, _ in self.interface_state_totals:
                    definitions.append(
                        {
                            "producer": self.producer,
                            "measurable": self.interface_state,
                            "parameter": state,
                            "entity": entity.name,
                            "type": "Network",
                            "cumulative": False,
                            "description": f"Number of swp interfaces in the {state} interface operation state",
                        }
                    )
        interfaces = self._nvue_interfaces(now, entity)
        if bool(interfaces):
            definitions += interfaces
        return True, definitions

    def sample(self, now, entity, pool=None, asynchronous=True, follow_up=None):
        values = []
        io_counters = self._io_counters()
        if bool(self._cmdaemon) and bool(self._cmdaemon._device):
            port_speeds = self._cmdaemon._device.port_speeds
        else:
            port_speeds = None
        if io_counters:
            now = self._timestamp_in_milliseconds(now)
            if bool(self._cmdaemon):  # TODO: not samplenow
                for timestamp, element in self._cmdaemon.get_interface_states():
                    name = element.get("name", None)
                    if name is None or name in self.excludeIf:
                        continue
                    timestamp = int(timestamp * 1000)
                    if timestamp == now:
                        continue
                    value = 1 if element.get("up", False) else 0
                    values.append(
                        {
                            "producer": self.producer,
                            "timestamp": timestamp,
                            "measurable": self.interface_state,
                            "parameter": name,
                            "entity": entity.name,
                            "raw": value,
                            "rate": value,
                        }
                    )

            swp_ports = set()
            operstate_counts = {index: 0 for _, index in self.interface_state_totals}
            totals = {name: 0 for name, _, _, _ in self._network_io_info}
            for interface, io in io_counters.items():
                if self._exclude(interface):
                    continue
                try:
                    with open(f"/sys/class/net/{interface}/operstate") as fd:
                        if fd.read().strip() in self.up_states:
                            value = 1
                        else:
                            value = 0
                except IOError:
                    value = 2
                values.append(
                    {
                        "producer": self.producer,
                        "timestamp": now,
                        "measurable": self.interface_state,
                        "parameter": interface,
                        "entity": entity.name,
                        "raw": value,
                        "rate": value,
                    }
                )
                if interface.startswith("swp"):
                    swp_ports.add(interface)
                    operstate_counts[value] += 1
                    operstate_counts[self.interface_state_total] += 1
                for name, item, _, _ in self._network_io_info:
                    try:
                        value = getattr(io, item)
                        values.append(
                            {
                                "producer": self.producer,
                                "timestamp": now,
                                "measurable": name,
                                "parameter": interface,
                                "entity": entity.name,
                                "raw": value,
                                "rate": value,
                            }
                        )
                        if interface.startswith("swp"):
                            totals[name] += value
                    except AttributeError:
                        pass
            if bool(swp_ports):
                if bool(port_speeds):
                    for interface in swp_ports:
                        value = port_speeds.get(interface, None)
                        values.append(
                            {
                                "producer": self.producer,
                                "timestamp": now,
                                "measurable": "ReportedSpeed",
                                "parameter": interface,
                                "entity": entity.name,
                                "raw": value,
                                "rate": value,
                            }
                        )
                for state, index in self.interface_state_totals:
                    values.append(
                        {
                            "producer": self.producer,
                            "timestamp": now,
                            "measurable": self.interface_state,
                            "parameter": state,
                            "entity": entity.name,
                            "raw": operstate_counts[index],
                            "rate": operstate_counts[index],
                        }
                    )
                for name, _, _, _ in self._network_io_info:
                    total = totals.get(name, 0)
                    values.append(
                        {
                            "producer": self.producer,
                            "timestamp": now,
                            "measurable": name,
                            "parameter": "total",
                            "entity": entity.name,
                            "raw": total,
                            "rate": total,
                        }
                    )
        interfaces = self._nvue_interfaces(now, entity)
        if bool(interfaces):
            values += interfaces
        return True, [Value(it) for it in values]
