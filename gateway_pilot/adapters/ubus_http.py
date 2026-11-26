"""Read-only rpcd/ubus JSON-RPC transport for a loopback router (the OpenWrt lab).

The account and its ACL live on the router; this client only logs in and calls
the methods it is given. It refuses non-loopback URLs so credentials never
leave the machine. Not board validation: the lab routers are QEMU VMs.
"""
from __future__ import annotations

import json
import urllib.request
from ipaddress import ip_address
from pathlib import Path
from urllib.parse import urlsplit

_NO_SESSION = "0" * 32


class UbusHttpError(RuntimeError):
    pass


class UbusHttpReadTransport:
    def __init__(self, url: str, username: str, password_file: Path, *, timeout_s: float = 5):
        parts = urlsplit(url)
        host = parts.hostname or ""
        try:
            loopback = host == "localhost" or ip_address(host).is_loopback
        except ValueError:
            loopback = False
        if parts.scheme != "http" or not loopback or parts.path != "/ubus":
            raise ValueError("ubus_http_requires_loopback_url")
        self.url, self.username, self.timeout_s = url, username, timeout_s
        self._password_file = Path(password_file)
        self._session: str | None = None

    def _rpc(self, session: str, obj: str, method: str, args: dict) -> list:
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "call",
                           "params": [session, obj, method, args]}).encode()
        request = urllib.request.Request(self.url, body, {"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
            reply = json.load(response)
        result = reply.get("result") if isinstance(reply, dict) else None
        if not isinstance(result, list) or not result or result[0] != 0:
            raise UbusHttpError(f"ubus_call_failed:{obj}.{method}")
        return result

    def _login(self) -> str:
        if self._session is None:
            password = self._password_file.read_text(encoding="utf-8").strip()
            result = self._rpc(_NO_SESSION, "session", "login",
                               {"username": self.username, "password": password})
            session = result[1].get("ubus_rpc_session") if len(result) > 1 else None
            if not isinstance(session, str):
                raise UbusHttpError("ubus_login_failed")
            self._session = session
        return self._session

    def probe(self, object_name: str, method_name: str) -> bool:
        """True only when the router answers this read for this account.

        rpcd's ``session access`` needs its own ACL grant, which the read-only
        account deliberately lacks, so the probe is the read itself.
        """
        try:
            self.read(object_name, method_name, {})
        except UbusHttpError:
            return False
        return True

    def read(self, object_name: str, method_name: str, arguments: dict) -> dict:
        result = self._rpc(self._login(), object_name, method_name, dict(arguments))
        value = result[1] if len(result) > 1 else {}
        if not isinstance(value, dict):
            raise UbusHttpError("ubus_unstructured_response")
        return value
