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

from uuid import UUID

from cm_lite_daemon.certificate.certificate import Certificate
from cm_lite_daemon.certificate.csr import CSR
from cm_lite_daemon.certificate.private_key import Private_Key
from cm_lite_daemon.http_connection import HTTP_Connection
from cm_lite_daemon.rpc.rpc import RPC
from cm_lite_daemon.tools.exit_codes import ExitCodes


def generate_certificate(settings, logger, bits, common_name, domains):
    key = Private_Key()
    key.generate(bits=bits)

    csr = CSR(key)
    csr.generate(common_name=common_name, domains=domains)

    connection = HTTP_Connection(settings, logger)
    if connection.register_session() is None:
        logger.warning("Unable to register session for certificate request")
        return ExitCodes.REGISTER_SESSION
    elif connection.session_uuid == str(UUID(int=0)):
        logger.warning("Register session failed")
        return ExitCodes.ZERO_SESSION

    rpc = RPC(settings)
    code, request_uuid = rpc.call(
        service="cmcert",
        call="requestCertificate",
        args=[
            csr.get_pem(),
            connection.session_uuid,
            HTTP_Connection.CLIENT_TYPE_LITE_INSTALLER,
        ],
    )
    if bool(code):
        logger.warning("Unable to get request certificate: (%d) %s", (code, request_uuid))
        return ExitCodes.REQUEST_CERTIFICATE
    elif request_uuid == str(UUID(int=0)):
        logger.warning("Unable to get request certificate, no UUID")
        return ExitCodes.REQUEST_CERTIFICATE
    logger.info(f"Certificate requested: {request_uuid}, waiting for it to be issued...")
    event = connection.wait_for_event(["NewCertificateEvent", "CertificateDeniedEvent", "EndOfSessionEvent"])
    exit_code = ExitCodes.NO_CERTIFICATE
    if "certificate" in event:
        certificate = Certificate(pem=event["certificate"])
        if certificate.valid():
            if not key.save(settings.key_file):
                logger.warning(f"Failed to saved private key: {settings.key_file}")
                exit_code = ExitCodes.SAVE_FAILED
            elif not certificate.save(settings.cert_file):
                logger.warning(f"Failed to save certificate: {settings.cert_file}")
                exit_code = ExitCodes.SAVE_FAILED
            else:
                logger.info(f"Saved private key: {settings.key_file}")
                logger.info(f"Saved certificate: {settings.cert_file}")
                exit_code = ExitCodes.OK
        else:
            logger.warning("Received an invalid certificate")
    else:
        logger.warning("No certificate received")
    connection.unregister_session()
    return exit_code
