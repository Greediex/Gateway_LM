"""Local HTTP Linux dispatch never accepts execution configuration from JSON."""
import http.client
import json
import threading
import unittest
from unittest.mock import patch

from web_gateway import server


class LaptopHTTPTests(unittest.TestCase):
    def setUp(self):
        self.httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        self.httpd.default_source = "live"
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.close_server)
        for target, value in (("web_gateway.server.platform.system", "Linux"), ("web_gateway.server.os.name", "posix")):
            p = patch(target, return_value=value) if target.endswith("system") else patch(target, value)
            p.start(); self.addCleanup(p.stop)

    def close_server(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2)

    def post(self, payload, endpoint="/api/network", headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.httpd.server_port, timeout=3)
        try:
            connection.request("POST", endpoint, json.dumps(payload),
                               headers={"Content-Type": "application/json", **(headers or {})})
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def test_empty_network_request_calls_only_trusted_application(self):
        with patch("gateway_pilot.application.diagnose_network.diagnose_network", return_value={"mode": "linux_live"}) as diagnose:
            status, body = self.post({})
        self.assertEqual((status, body), (200, {"mode": "linux_live"}))
        diagnose.assert_called_once_with()

    def test_network_rejects_all_supplied_execution_options(self):
        with patch("gateway_pilot.application.diagnose_network.diagnose_network") as diagnose:
            for data in ({"backend": "unsafe"}, {"target": "remote"}, {"permissions": ["write"]}, [], None):
                with self.subTest(data=data):
                    self.assertEqual(self.post(data)[0], 400)
            diagnose.assert_not_called()

    def test_network_requires_linux_live_mode(self):
        with patch("gateway_pilot.application.diagnose_network.diagnose_network") as diagnose:
            self.httpd.default_source = "replay"
            self.assertEqual(self.post({})[0], 400)
            self.httpd.default_source = "live"
            with patch("web_gateway.server.platform.system", return_value="Windows"):
                self.assertEqual(self.post({})[0], 400)
            diagnose.assert_not_called()

    def test_local_host_origin_and_content_type_guards_precede_application(self):
        with patch("gateway_pilot.application.diagnose_network.diagnose_network") as diagnose:
            for headers, expected in (({"Host": "attacker.invalid"}, 403),
                                      ({"Origin": "https://attacker.invalid"}, 403),
                                      ({"Content-Type": "text/plain"}, 415)):
                with self.subTest(headers=headers):
                    self.assertEqual(self.post({}, headers=headers)[0], expected)
            diagnose.assert_not_called()

    def test_chat_forwards_only_bounded_request_and_registered_method(self):
        with patch("gateway_pilot.application.diagnose_network.chat_linux", return_value={"answer": "verified"}) as chat:
            status, result = self.post({"message": "  Wi-Fi thế nào?  ", "method": "bm25", "with_llm": False,
                                        "model": "ignored", "fixture_id": "ignored"}, "/api/chat")
        self.assertEqual((status, result), (200, {"answer": "verified"}))
        chat.assert_called_once_with("Wi-Fi thế nào?", method="bm25")

    def test_live_llm_routes_to_existing_skill_session_with_server_model(self):
        with patch("gateway_pilot.application.skill_chat.CHAT") as chat:
            chat.chat.return_value={"answer":"verified","catalog_total":120}
            status,result=self.post({"message":"  Wi-Fi thế nào?  ","with_llm":True,
                                     "session_id":"a"*32,"model":"untrusted-ignored"},"/api/chat")
        self.assertEqual(status,200)
        self.assertEqual(result["catalog_total"],120)
        chat.chat.assert_called_once_with("Wi-Fi thế nào?",session_id="a"*32)

    def test_chat_rejects_backend_target_permissions_and_commands(self):
        with patch("gateway_pilot.application.diagnose_network.chat_linux") as chat:
            for key in ("backend", "adapter", "target", "permissions", "command", "interface", "world", "approved_digest"):
                with self.subTest(key=key):
                    self.assertEqual(self.post({"message": "check", key: "injected"}, "/api/chat")[0], 400)
            chat.assert_not_called()

    def test_skill_chat_busy_and_expired_errors_keep_machine_readable_reason(self):
        from gateway_pilot.application.skill_launcher import SkillSessionError
        with patch('gateway_pilot.application.skill_chat.CHAT') as chat:
            for reason,expected in [('session_busy',409),('model_busy',429),
                                    ('session_capacity_limit',429),('session_expired',410)]:
                with self.subTest(reason=reason):
                    chat.chat.side_effect=SkillSessionError(reason)
                    status,body=self.post({'message':'Kiểm tra DNS','with_llm':True},'/api/chat')
                    self.assertEqual(status,expected)
                    self.assertEqual(body['reason'],reason)
                    self.assertTrue(body['error'])
