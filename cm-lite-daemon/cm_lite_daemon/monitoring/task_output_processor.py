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

from cm_lite_daemon.monitoring.parser.sample_json import Sample_JSON
from cm_lite_daemon.monitoring.parser.sample_text import Sample_text
from cm_lite_daemon.monitoring.parser.sample_yaml import Sample_YAML
from cm_lite_daemon.monitoring.parser.single_line import Single_Line
from cm_lite_daemon.monitoring.parser.text_typer import Text_Typer


class Task_Output_Processor:
    def __init__(self, cmdaemon, logger, enum_value_cache=None, translator=None):
        self._cmdaemon = cmdaemon
        self._logger = logger
        self._enum_value_cache = enum_value_cache
        self._translator = translator

    def process(self, runner, producer, expected_format, now, entity, name=None, arguments=None):
        parser = None
        if runner.output is not None:
            typer = Text_Typer()
            detected_format = typer.determine_format(runner.output, expected_format)
            if detected_format == Text_Typer.TEXT:
                parser = Sample_text(producer, entity.name, self._enum_value_cache)
            elif detected_format == Text_Typer.JSON:
                parser = Sample_JSON(producer, entity.name, self._enum_value_cache)
            elif detected_format == Text_Typer.YAML:
                parser = Sample_YAML(producer, entity.name, self._enum_value_cache)
            elif (detected_format == Text_Typer.METRIC) or (detected_format == Text_Typer.CHECK):
                parser = Single_Line(
                    producer,
                    entity.name,
                    name,
                    " ".join(arguments),
                    self._enum_value_cache,
                )
            else:
                self._logger.debug(
                    f"Unable to determine format for {runner.command} ({producer}) based on {len(runner.output)} bytes"
                )
        if parser is not None:
            values = parser.parse(runner.output, now, runner.info)
            self._logger.debug(
                f"New values: {len(values)} based on {len(runner.output)} bytes (now: {now}) (type {detected_format})"
            )
            self._translator.push(values)
