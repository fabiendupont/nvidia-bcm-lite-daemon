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


import logging
import platform
import signal


class Signal_Handler:
    def __init__(self):
        self._cmdaemon = None
        self._logger = None
        self.original_sigint_handler = None
        self.original_sigusr1_handler = None
        self.original_sigusr2_handler = None

    def __enter__(self):
        def sigint_handler(signum, frame):
            if self._cmdaemon:
                self._cmdaemon.stop()
            else:
                self._logger.warning("Pressed ctrl-C (no cmdaemon)")

        self.original_sigint_handler = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, sigint_handler)

        if platform.system() == "Linux":

            def sigusr1_handler(signum, frame):
                self._logger.info("Turn on debug")
                self._logger.setLevel(logging.DEBUG)

            self.original_sigusr1_handler = signal.getsignal(signal.SIGUSR1)
            signal.signal(signal.SIGUSR1, sigusr1_handler)

            def sigusr2_handler(signum, frame):
                self._logger.info("Turn off debug")
                self._logger.setLevel(logging.INFO)

            self.original_sigusr2_handler = signal.getsignal(signal.SIGUSR2)
            signal.signal(signal.SIGUSR2, sigusr2_handler)

        return self

    def __exit__(self, type, value, tb):
        self.release()

    def release(self):
        if self.original_sigint_handler is None:
            return False
        signal.signal(signal.SIGINT, self.original_sigint_handler)
        self.original_sigint_handler = None
        if platform.system() == "Linux":
            signal.signal(signal.SIGUSR1, self.original_sigusr1_handler)
            self.original_sigusr1_handler = None
            signal.signal(signal.SIGUSR2, self.original_sigusr2_handler)
            self.original_sigusr2_handler = None
        return True
