"""IPv4 ICMP sampling using the Windows IP Helper API."""

import ctypes
import sys
from ctypes.wintypes import BOOL, DWORD, HANDLE, WORD
from ipaddress import IPv4Address
from struct import unpack_from
from time import sleep


SAMPLE_COUNT = 4
TIMEOUT_MS = 1200
# Destination unreachable, timeout, or an expired TTL counts as no echo reply.
NO_REPLY = {11002, 11003, 11004, 11005, 11010, 11013, 11014}


def sample_echo(address, source):
    api = ctypes.WinDLL("iphlpapi.dll", use_last_error=True)
    api.IcmpCreateFile.argtypes = []
    api.IcmpCreateFile.restype = HANDLE
    api.IcmpCloseHandle.argtypes = [HANDLE]
    api.IcmpCloseHandle.restype = BOOL
    send = api.IcmpSendEcho2Ex
    pointer = ctypes.c_void_p
    send.argtypes = [HANDLE, HANDLE, pointer, pointer, DWORD, DWORD, pointer, WORD,
                     pointer, pointer, DWORD, DWORD]
    send.restype = DWORD
    destination = int.from_bytes(IPv4Address(address).packed, sys.byteorder)
    source_address = int.from_bytes(IPv4Address(source).packed, sys.byteorder)
    payload = ctypes.create_string_buffer(b"Gateway LM")
    buffer = ctypes.create_string_buffer(512)
    handle = api.IcmpCreateFile()
    if not handle or handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())

    rtt_ms = []
    try:
        for index in range(SAMPLE_COUNT):
            count = send(handle, None, None, None, source_address, destination,
                         payload, len(payload) - 1, None, buffer, len(buffer), TIMEOUT_MS)
            if count:
                # The first three DWORDs of ICMP_ECHO_REPLY are address, status and RTT.
                responder, status, rtt = unpack_from("<III", buffer)
                if status == 0 and responder == destination:
                    rtt_ms.append(rtt)
            else:
                error = ctypes.get_last_error()
                if error not in NO_REPLY:
                    raise ctypes.WinError(error)
            if index + 1 < SAMPLE_COUNT:
                sleep(0.2)
    finally:
        api.IcmpCloseHandle(handle)
    received = len(rtt_ms)
    return {"address": address, "replies": bool(received), "sent": SAMPLE_COUNT,
            "received": received, "loss_pct": 100 * (SAMPLE_COUNT - received) / SAMPLE_COUNT,
            "rtt_ms": rtt_ms}
