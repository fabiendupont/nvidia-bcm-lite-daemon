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
from uuid import UUID

from cm_lite_daemon.base import Base
from cm_lite_daemon.monitoring.execution_filter import Execution_Filter
from cm_lite_daemon.monitoring.execution_multiplexer import Execution_Multiplexer
from cm_lite_daemon.monitoring.sampler.cmdaemon_state_sampler_task import CMDaemon_State_Sampler_Task
from cm_lite_daemon.monitoring.sampler.cpu_usage_sampler_task import CPU_Usage_Sampler_Task
from cm_lite_daemon.monitoring.sampler.disk_io_sampler_task import Disk_IO_Sampler_Task
from cm_lite_daemon.monitoring.sampler.disk_space_sampler_task import Disk_Space_Sampler_Task
from cm_lite_daemon.monitoring.sampler.health_check_script_sampler_task import Health_Check_Script_Sampler_Task
from cm_lite_daemon.monitoring.sampler.meminfo_sampler_task import MemInfo_Sampler_Task
from cm_lite_daemon.monitoring.sampler.metric_script_sampler_task import Metric_Script_Sampler_Task
from cm_lite_daemon.monitoring.sampler.network_io_sampler_task import Network_IO_Sampler_Task
from cm_lite_daemon.monitoring.sampler.process_sampler_task import Process_Sampler_Task
from cm_lite_daemon.monitoring.sampler.script_sampler_task import Script_Sampler_Task
from cm_lite_daemon.monitoring.sampler.sysinfo_sampler_task import SysInfo_Sampler_Task


class DataProducer(Base):
    def __init__(self, cmdaemon, data=None):
        self._cmdaemon = cmdaemon
        self.uuid = UUID(int=0)
        self.interval = 0
        self.offset = 0
        self.name = ""
        self._original_name = ""
        self.disabled = False
        self.script = None
        self.nodeExecutionFilters = []
        self.executionMultiplexers = []
        if data is not None:
            super().__init__(data)
            self.normalize()

    def normalize(self):
        if isinstance(self.uuid, str):
            self.uuid = UUID(self.uuid)
        self._original_name = self.name
        self.name = self.name.lower()
        self.nodeExecutionFilters = [Execution_Filter(it) for it in self.nodeExecutionFilters]
        self.executionMultiplexers = [Execution_Multiplexer(it) for it in self.executionMultiplexers]

    def filtered(self):
        # return true if allowed to run
        if len(self.nodeExecutionFilters) == 0:
            return True
        return any(it.filtered(self._cmdaemon) for it in self.nodeExecutionFilters)

    def allowed(self):
        return hasattr(self, "when") and (self.when == "TIMED")

    def _has_script(self):
        return hasattr(self, "script") and bool(self.script) and os.path.exists(self.script)

    def get_sampler(self):
        sampler = None
        if self.disabled:
            self._cmdaemon._logger.debug(f"Disabled sampler: {self.name}")
        elif not self.allowed():
            self._cmdaemon._logger.debug(f"Not allowed sampler: {self.name}")
        elif not self.filtered():
            self._cmdaemon._logger.debug(f"Filtered sampler: {self.name}")
        elif not hasattr(self, "childType"):
            self._cmdaemon._logger.debug(f"Invalid sampler: {self.name}")
        elif self.childType == "MonitoringDataProducerScript":
            if self._has_script():
                self._cmdaemon._logger.debug(f"Create sampler: {self.name} ({self.script})")
                sampler = Script_Sampler_Task(
                    cmdaemon=self._cmdaemon,
                    script=self.script,
                    producer=self.uuid,
                    interval=self.interval,
                    offset=self.offset,
                    arguments=self.arguments,
                    timeout=self.timeout,
                )
            else:
                self._cmdaemon._logger.debug(f"Could not create script sampler: {self.name}")
        elif self.childType == "MonitoringDataProducerSingleLineMetricScript":
            if self._has_script():
                self._cmdaemon._logger.debug(f"Create sampler: {self.name} ({self.script})")
                sampler = Metric_Script_Sampler_Task(
                    cmdaemon=self._cmdaemon,
                    script=self.script,
                    producer=self.uuid,
                    interval=self.interval,
                    offset=self.offset,
                    arguments=self.arguments,
                    timeout=self.timeout,
                    name=self.name,
                    description=self.description,
                    unit=self.unit,
                    typeClass=self.typeClass,
                    minimum=self.minimum,
                    maximum=self.maximum,
                )
            else:
                self._cmdaemon._logger.debug(f"Could not create script sampler: {self.name}")
        elif self.childType == "MonitoringDataProducerSingleLineHealthCheckScript":
            if self._has_script():
                self._cmdaemon._logger.debug(f"Create sampler: {self.name} ({self.script})")
                sampler = Health_Check_Script_Sampler_Task(
                    cmdaemon=self._cmdaemon,
                    script=self.script,
                    producer=self.uuid,
                    interval=self.interval,
                    offset=self.offset,
                    arguments=self.arguments,
                    timeout=self.timeout,
                    name=self._original_name,
                    description=self.description,
                    typeClass=self.typeClass,
                )
            else:
                self._cmdaemon._logger.debug(f"Could not create script sampler: {self.name}")
        elif self.childType == "MonitoringDataProducerCMDaemonState":
            self._cmdaemon._logger.debug(f"Create cmdaemon state sampler: {self.name}")
            sampler = CMDaemon_State_Sampler_Task(
                self._cmdaemon, interval=self.interval, offset=self.offset, producer=self.uuid
            )
        elif self.childType == "MonitoringDataProducerSysInfo":
            self._cmdaemon._logger.debug(f"Create system info sampler: {self.name}")
            sampler = SysInfo_Sampler_Task(interval=self.interval, offset=self.offset, producer=self.uuid)
        elif self.childType == "MonitoringDataProducerProcMemInfo":
            self._cmdaemon._logger.debug(f"Create memory info sampler: {self.name}")
            sampler = MemInfo_Sampler_Task(interval=self.interval, offset=self.offset, producer=self.uuid)
        elif self.childType == "MonitoringDataProducerProcMount":
            self._cmdaemon._logger.debug(f"Create disk space sampler: {self.name}")
            sampler = Disk_Space_Sampler_Task(
                interval=self.interval,
                offset=self.offset,
                producer=self.uuid,
                excludeMountPoints=self.excludeMountPoints,
            )
        elif self.childType == "MonitoringDataProducerSysBlockStat":
            self._cmdaemon._logger.debug(f"Create disk IO sampler: {self.name}")
            sampler = Disk_IO_Sampler_Task(
                interval=self.interval,
                offset=self.offset,
                producer=self.uuid,
                excludeVirtualDisks=self.excludeVirtualDisks,
                excludeDisks=self.excludeDisks,
            )
        elif self.childType == "MonitoringDataProducerProcNetDev":
            self._cmdaemon._logger.debug(f"Create network IO sampler: {self.name}")
            sampler = Network_IO_Sampler_Task(
                self._cmdaemon,
                interval=self.interval,
                offset=self.offset,
                producer=self.uuid,
                excludeIf=self.excludeIf,
            )
        elif self.childType == "MonitoringDataProducerProcPidStat":
            self._cmdaemon._logger.debug(
                f"Create process sampler: {self.name}, pid: {int(self.pid)}, process: {self.process}"
            )
            sampler = Process_Sampler_Task(
                interval=self.interval,
                offset=self.offset,
                producer=self.uuid,
                pid=self.pid,
                process=self.process,
            )
        elif self.childType == "MonitoringDataProducerProcStat":
            self._cmdaemon._logger.debug("Create CPU usage sampler")
            sampler = CPU_Usage_Sampler_Task(
                interval=self.interval,
                offset=self.offset,
                producer=self.uuid,
                per_cpu=self.individualCPU,
            )
        else:
            self._cmdaemon._logger.debug(f"Unhandled sampler: {self.name} ({self.childType})")
        return sampler
