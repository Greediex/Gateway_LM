"""End-to-end iGate snapshot, evidence, display-only commands and Web contracts."""
import io
import json
import re
import shutil
import tempfile
import unittest
from hashlib import sha256
from http import HTTPStatus
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from jsonschema import Draft202012Validator

from gateway_pilot.adapters.results import ToolResult
from gateway_pilot.application import skill_chat
from gateway_pilot.application.igate_proposal import NOTICE as PROPOSAL_NOTICE, resolve_device
from gateway_pilot.application.replay_sim_run import run_replay_skill
from gateway_pilot.application.skill_launcher import SkillLauncher
from gateway_pilot.command_catalog import session as read_session
from gateway_pilot.command_catalog.runtime import ReadRuntime
from gateway_pilot.core import PlanError, ROOT
from gateway_pilot.graph_v3.runner import GraphRunner
from gateway_pilot.skill_expansion import deployment as dep, igate_data, replay_sim
from gateway_pilot.skill_expansion.coverage import coverage_report, skill_graph
from gateway_pilot.skill_expansion.igate_snapshot import read_snapshot
from web_gateway.server import Handler


BASE = b'ts: 2026-11-20T07:00:00Z\nmode: demo\n'
MAC = '02:00:00:00:00:01'


class IgateSnapshotTests(unittest.TestCase):
    def test_vendor_pin_and_sanitization(self):
        path = igate_data.VENDOR / 'PROVENANCE.json'
        self.assertEqual(sha256(path.read_bytes()).hexdigest(),
                         '64ae97acfeb2eb29bdc83eb9c6ad5b048e4cd715e8d43547aad0d6a8d480d232')
        manifest, contents = igate_data.vendor_data()
        self.assertEqual(manifest['source_commit'], 'c00fe2e81ddcad2784bb4f641bd2a152861385fe')
        self.assertEqual(len(contents), 50)
        name = 'examples/router_snapshot.example.yaml'
        record = manifest['files'][name]
        self.assertNotEqual(record['source_sha256'], record['vendored_sha256'])
        self.assertIn('password', record['sanitization'])
        rows = contents[name].decode().split('encryption password\n', 1)[1].split('clients: |', 1)[0].splitlines()
        self.assertEqual([row.split()[-1] for row in rows], ['-', '-', '-'])
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / 'igate'
            shutil.copytree(igate_data.VENDOR, folder)
            (folder / name).write_bytes(contents[name] + b'# drift')
            with self.assertRaisesRegex(PlanError, 'igate_vendor_pin'):
                igate_data.vendor_data(folder)

    def test_whitespace_columns_missing_values_and_password_projection(self):
        _, data = read_snapshot(BASE + b'''
clients_count: 1
clients: |
  name mac ip rssi_dbm snr_db tx_mbps rx_mbps
  Living_Room 02-00-00-00-00-01 192.0.2.1 - -3 - 0
wifi:
  ssids: |
    ssid password network enabled
    Guest sentinel-secret guest 0
feed: {qos: 1}
qos: |
  ip name class session_s flows
''')
        device = data['device.telemetry']['clients'][0]
        self.assertEqual(device, {'mac': MAC, 'ip': '192.0.2.1', 'name': 'Living Room', 'rx_mbps': 0, 'snr_db': -3})
        self.assertEqual(data['router.telemetry'], {'guest_enabled': False})
        self.assertEqual(data['traffic.application_sessions']['sessions'], [])
        self.assertTrue(data['traffic.application_sessions']['sessions_complete'])
        self.assertNotIn('sentinel-secret', json.dumps(data))
        self.assertNotIn('password', json.dumps(data))
        self.assertEqual(resolve_device(data['device.find'], 'Living Room')['mac'], MAC)

    def test_unknown_never_becomes_zero_or_off(self):
        _, data = read_snapshot(BASE + b'''
clients_count: '-'
clients: '-'
sys: {temp_c: -1, cpu_pct: 300, mem_pct: '-'}
wan: {up: 1, ping_ms: '-', internet: '-'}
wifi:
  ssids: |
    band ssid network enabled hidden encryption password
    2g Home lan 1 0 psk2 -
policy_rows: |
  mac kind dl_kbps ul_kbps scheds
  02:00:00:00:00:01 block - - -
qos: |
  ip name class session_s flows
  192.0.2.10 Device GAMING 30 1
''')
        self.assertEqual(data['device.find'], {})
        self.assertEqual(data['router.telemetry'], {'wan_up': True})
        self.assertEqual(data['traffic.application_sessions'], {})
        self.assertEqual(data['schedule.list'], {})
        _, data = read_snapshot(BASE + b'feed: {qos: 0}\nqos: |\n  ip class\n  192.0.2.10 GAMING\n')
        self.assertEqual(data['traffic.application_sessions'], {'qos_available': False})

    def test_incomplete_or_ambiguous_identity_asks_instead_of_guessing(self):
        _, data = read_snapshot(BASE + b'''
clients_count: 2
clients_truncated: 0
clients: |
  mac name label
  02:00:00:00:00:01 device-1 TV
  02:00:00:00:00:02 TV living_room
''')
        self.assertIsNone(resolve_device(data['device.find'], 'TV'))
        self.assertIsNone(resolve_device(data['device.find'], 'unlisted'))
        self.assertEqual(resolve_device(data['device.find'], '02-00-00-00-00-01')['mac'], MAC)
        _, data = read_snapshot(BASE + b'clients: |\n  name mac\n  phone 02:00:00:00:00:01\n  phone 02:00:00:00:00:01\n')
        self.assertIsNone(resolve_device(data['device.find'], MAC))

    def test_malformed_snapshots_and_unmapped_qos(self):
        for raw in (BASE.replace(b'demo', b'live'), BASE + b'mode: demo\n',
                    BASE + b'clients: |\n  name mac\n  short\n'):
            with self.subTest(data=raw), self.assertRaises(PlanError):
                read_snapshot(raw)
        _, values = read_snapshot(BASE + b'feed: {qos: 1}\nqos: |\n  ip class\n  192.0.2.10 GAMING\n')
        self.assertEqual(values['traffic.application_sessions'],
                         {'qos_available': True, 'sessions_complete': False, 'sessions': []})


class IgateReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile = replay_sim.prepare_profile()
        cls.schema = json.loads(cls.profile.igate_vendor['contracts/firmware-command-v1.schema.json'])

    def setUp(self):
        self.model = Mock(side_effect=AssertionError('iGate turn must be deterministic'))
        self.launcher = SkillLauncher()
        self.chat = skill_chat.SkillChat(self.launcher, model_factory=self.model)
        profile_patch = patch.object(replay_sim, 'prepare_profile', return_value=self.profile)
        profile_patch.start()
        self.addCleanup(profile_patch.stop)
        read = dep.read_json

        def approve(path):
            doc = read(path)
            if Path(path).name == 'approvals.json':
                doc['replay_sim'] = self.profile.approval.copy()
            return doc

        approval_patch = patch.object(dep, 'read_json', side_effect=approve)
        approval_patch.start()
        self.addCleanup(approval_patch.stop)

    def _turn(self, question, sid=None, scenario=None):
        return self.chat.chat(question, mode='replay_sim', session_id=sid, scenario=scenario)

    def test_gold_is_separate_and_all_fifteen_replays_use_scoped_core(self):
        gold = json.loads((igate_data.SCENARIOS / 'gold.json').read_text())
        self.assertEqual(set(gold), set(replay_sim.STATES))
        real_open = io.open

        def no_gold(path, *args, **kwargs):
            if not isinstance(path, int) and Path(path).name.startswith('gold'):
                self.fail(f'runtime opened {path}')
            return real_open(path, *args, **kwargs)

        with patch('io.open', side_effect=no_gold), patch.object(
                read_session, 'execute_ready_once', wraps=read_session.execute_ready_once) as kernel, patch.object(
                GraphRunner, 'step', autospec=True, side_effect=GraphRunner.step) as step:
            for state, cases in gold.items():
                self.assertEqual(set(cases), set(self.profile.igate.actions))
                for sid, (verdict, true_claims) in cases.items():
                    with self.subTest(state=state, sid=sid):
                        row = run_replay_skill(replay_sim.ReplaySession(self.profile, state), 'test', sid, deadline=None)
                        claims = {cid: c for cid, c in row['assessment']['claims'].items() if c['value'] == 'TRUE'}
                        self.assertEqual((row['verdict'], sorted(claims)), (verdict, true_claims))
                        self.assertEqual(row['calls_this_run'], int(state != 'missing'))
                        if state != 'missing':
                            fact, = row['evidence']
                            self.assertEqual((fact['scope'], fact['target'], fact['source']),
                                             ('gateway', replay_sim.TARGET, replay_sim.SimulationReplayBackend.source))
                            self.assertEqual(row['timeline'][0]['node_state'], 'SUCCEEDED')
                            self.assertTrue(all(c['evidence'] == [fact['id']] for c in claims.values()))
                        else:
                            self.assertEqual(row['evidence'], [])
            self.assertGreaterEqual(kernel.call_count, 10)
            self.assertEqual(step.call_count, 10)

    def test_quick_answers_use_verified_data_even_with_model_slot_busy(self):
        reads = {
            'Có bao nhiêu thiết bị online?': ('IG01', 'Có 3 thiết bị'),
            'CPU/RAM/nhiệt độ': ('IG03', 'CPU: 17%, RAM: 62%, Nhiệt độ: 54.5 °C'),
            'Ping bao nhiêu?': ('IG03', '12 ms'),
            'Có Internet không?': ('IG03', 'Router có Internet'),
            'Wi-Fi khách đang bật không?': ('IG03', 'đang tắt'),
            'Ai đang chơi game?': ('IG04', 'Máy tính bảng của con'),
        }
        sid = self.launcher.create_session('replay_sim')['session_id']
        clock_before = self.chat.clock()
        with skill_chat._MODEL_SLOT:
            for question, (skill, snippet) in reads.items():
                with self.subTest(question=question):
                    response = self._turn(question, sid)
                    self.assertEqual((response['answer_kind'], response['routing']['plan'],
                                      response['calls'], response['model_calls']), ('instant', [skill], 1, 0))
                    self.assertIn(snippet, response['answer'])
                    self.assertIn(replay_sim.NOTICE, response['answer'])
                    self.assertEqual(response['timeline'][0]['status'], 'OK')
                    self.assertGreater(response['timings_ms']['total'], 0)
                    self.assertGreaterEqual(response['timings_ms']['total'], response['timings_ms']['execution'])
        self.assertGreater(self.chat.clock(), clock_before)
        self.model.assert_not_called()

    def test_read_rendering_and_failure_messages(self):
        sid = self.launcher.create_session('replay_sim')['session_id']
        for question, snippet in [('Ai đang online?', 'TV phòng khách'),
                                  ('Chi tiết thiết bị SON-iPad', MAC),
                                  ('Tín hiệu và tốc độ của SON-iPad', '-52 dBm'),
                                  ('Chất lượng kết nối', 'Ping: 12 ms'),
                                  ('Kết quả speedtest', '301.2 Mbps'),
                                  ('Ai đang xem video?', 'TV phòng khách'),
                                  ('Ai đang gọi?', 'Laptop của bố'),
                                  ('Danh sách lịch', '0 lịch')]:
            with self.subTest(question=question):
                result = self._turn(question, sid)
                self.assertEqual(result['answer_kind'], 'evidence')
                self.assertIn(snippet, result['answer'])
                self.assertTrue(result['evidence'])
                self.assertIsNone(result['diagnosis'])
        result = self._turn('Ai đang chơi game?', scenario='fault')
        self.assertEqual(result['case_status'], 'UNAVAILABLE')
        self.assertIn('Không biết', result['answer'])
        self.assertNotIn('Máy tính bảng', result['answer'])
        self.assertEqual(result['evidence'][0]['value'], {'qos_available': False})
        fault = result['session_id']
        self.assertIn('2 lịch', self._turn('Danh sách lịch', fault)['answer'])
        self.assertIn('thất bại', self._turn('Kết quả speedtest', fault)['answer'])
        for query in ('Chi tiết thiết bị Laptop', 'Tín hiệu của unknown'):
            self.assertEqual(self._turn(query, fault)['case_status'], 'NEEDS_INPUT')
        result = self._turn('Có bao nhiêu thiết bị online?', scenario='missing')
        self.assertIn('Không biết', result['answer'])
        self.assertFalse(result['evidence'])
        self.assertNotIn('0 thiết bị', result['answer'])
        self.assertEqual(self._turn('Chạy speedtest ngay', sid)['calls'], 0)
        self.assertNotIn('command_proposal', self._turn('Mật khẩu Wi-Fi là gì?', sid))

    def test_curated_cache_and_bilingual_bm25_are_draft_without_evidence(self):
        sid = self.launcher.create_session('replay_sim')['session_id']
        for question, kind, method, passage in (
                ('Wi-Fi 8 là gì?', 'instant', 'igate_answer_cache', 'w8.vi.what'),
                ('What is Wi-Fi 8?', 'instant', 'igate_answer_cache', 'w8.en.what'),
                ('Cách tăng sóng Wi-Fi?', 'knowledge', 'igate_bm25', 'wb.vi.placement'),
                ('How can I improve Wi-Fi signal?', 'knowledge', 'igate_bm25', 'wb.en.placement')):
            with self.subTest(question=question), patch.object(self.launcher, 'run', side_effect=AssertionError):
                result = self._turn(question, sid)
                self.assertEqual((result['answer_kind'], result['routing']['method']), (kind, method))
                self.assertEqual(result['knowledge']['passages'], [passage])
                self.assertIn('kiến thức (draft)', result['answer'])
                self.assertEqual((result['evidence'], result['evidence_ids'], result['calls'], result['model_calls']),
                                 ([], [], 0, 0))
        self.model.assert_not_called()

    def test_eleven_firmware_proposals_match_contract_and_never_send(self):
        cases = [
            ('Chặn mạng của SON-iPad', 'device.block', 'block', {}, 'device'),
            ('Bỏ chặn mạng cho SON-iPad', 'device.resume', 'unblock', {}, 'device'),
            ('Chặn game trên SON-iPad', 'application.block', 'block', {'scope': 'application', 'application': 'GAMING'}, 'device'),
            ('Bỏ chặn gọi video trên SON-iPad', 'application.resume', 'unblock', {'scope': 'application', 'application': 'VIDEOCALL'}, 'device'),
            ('Ưu tiên xem video cho SON-iPad', 'qos.prioritize', 'optimize', {'application': 'VSTREAM'}, 'device'),
            ('Giới hạn SON-iPad tải xuống 20 Mbps và tải lên 5 Mbps', 'qos.rate_limit', 'limit',
             {'download_limit_mbps': 20, 'upload_limit_mbps': 5}, 'device'),
            ('Tắt Wi-Fi khách', 'network.guest_wifi', 'set_guest_wifi', {'enabled': False}, 'gateway'),
            ('Chặn SON-iPad trong 30 phút', 'device.schedule', 'block', {'schedule': {'duration_minutes': 30}}, 'device'),
            ('Hủy lịch số 7', 'schedule.cancel', 'cancel_schedule', {'schedule_id': 7}, 'schedules'),
            ('Tắt thiết bị SON-iPad', 'device.control', 'device_control', {'action': 'off'}, 'device'),
            ('Đổi ngôn ngữ sang tiếng Anh', 'ui.set_language', 'set_language', {'language': 'en'}, 'gateway'),
        ]
        sid = self.launcher.create_session('replay_sim')['session_id']
        with (patch('subprocess.Popen', side_effect=AssertionError('no shell command')) as shell,
              patch('socket.socket', side_effect=AssertionError('no network')) as socket,
              patch('gateway_pilot.graph_v3.change_transaction.SafeWriteTransaction',
                    side_effect=AssertionError('no WRITE controller')) as controller,
              patch.object(self.launcher, 'run', wraps=self.launcher.run) as run):
            for i, (question, skill, command, args, target) in enumerate(cases, 1):
                with self.subTest(skill=skill):
                    response = self._turn(question, sid)
                    self.assertEqual((response['case_status'], response['answer_kind']), ('PROPOSED', 'proposal'))
                    proposal = response['command_proposal']
                    envelope = proposal['envelope']
                    self.assertEqual(envelope, {'schema_version': '1.1' if i in (8, 9) else '1.0',
                        'request_id': i, 'command': command, 'arguments': args,
                        'target': {'type': target} | ({'selector': MAC} if target == 'device' else {})})
                    Draft202012Validator(self.schema).validate(envelope)
                    self.assertEqual(proposal['skill'], skill)
                    self.assertIs(proposal['executed'], False)
                    self.assertTrue(proposal['impact'])
                    self.assertIn(PROPOSAL_NOTICE, response['answer'])
                    self.assertEqual(response['model_calls'], 0)
                    if skill.startswith('application.') or skill == 'qos.prioritize':
                        self.assertIn('toàn bộ', proposal['impact'])
            self.assertEqual([call.args[1] for call in run.call_args_list], ['IG01'] * 8)
            shell.assert_not_called()
            socket.assert_not_called()
            controller.assert_not_called()
        self.assertNotIn('command_proposal', self.launcher.run(sid, 'device.block'))

    def test_missing_arguments_invalid_values_and_unsupported_scope(self):
        sid = self.launcher.create_session('replay_sim')['session_id']
        for query in ('Ưu tiên SON-iPad', 'Chặn người lạ', 'Chặn 192.0.2.10', 'Chặn 02:00:00:00:00:99',
                      'Hủy lịch', 'Hủy lịch số 0', 'Giới hạn SON-iPad', 'Giới hạn SON-iPad tải xuống 1.5 Mbps',
                      'Giới hạn SON-iPad tải xuống 10001 Mbps', 'Chặn SON-iPad trong 0 phút',
                      'Chặn SON-iPad từ 21:00 đến 06:00', 'Đổi ngôn ngữ sang Klingon',
                      'Chặn SON-iPad; Hủy lịch số 7'):
            with self.subTest(query=query):
                response = self._turn(query, sid)
                self.assertNotIn('command_proposal', response)
                self.assertIn(response['case_status'], {'NEEDS_INPUT', 'BLOCKED'})
        response = self._turn('Chặn SON-iPad từ 21:00 đến 06:00 mỗi ngày', sid)
        self.assertEqual(response['command_proposal']['envelope']['arguments'],
                         {'schedule': {'start_time': '21:00', 'end_time': '06:00', 'recurrence': 'daily'}})
        fault = self._turn('Chặn Laptop', scenario='fault')
        self.assertEqual(fault['case_status'], 'NEEDS_INPUT')
        self.assertNotIn('command_proposal', fault)
        self.assertNotIn('command_proposal', self._turn('Chặn SON-iPad', scenario='missing'))

    def test_core_rejects_wrong_scope_target_malformed_timeout_stale_and_denied(self):
        sid = self.launcher.create_session('replay_sim')['session_id']
        for defect in ('scope', 'target', 'schema', 'timeout', 'stale'):
            def sample(backend, metadata, arguments, context):
                if defect == 'timeout':
                    raise TimeoutError('test adapter timeout')
                rows = backend.sample_preview(metadata, arguments, context)
                corrupt = {'scope': {'scope': 'client'}, 'target': {'target': 'synthetic-other'},
                           'schema': {'value': {'online_count': 'broken'}},
                           'stale': {'age_s': 31}}[defect]
                return ToolResult(observations=(rows[0] | corrupt,))

            with self.subTest(defect=defect), patch.object(replay_sim.SimulationReplayBackend, 'sample', sample), \
                    patch.object(GraphRunner, 'step', autospec=True, side_effect=GraphRunner.step) as step:
                result = self._turn('Có bao nhiêu thiết bị online?', sid)
                step.assert_called()
                self.assertEqual((result['case_status'], result['evidence'], result['evidence_ids']),
                                 ('UNAVAILABLE', [], []))
                self.assertIn('Không biết', result['answer'])

        original = ReadRuntime.__init__

        def denied(runtime, *args, **kwargs):
            original(runtime, *args, **(kwargs | {'permissions': frozenset()}))

        with patch.object(ReadRuntime, '__init__', denied):
            result = self._turn('Chặn SON-iPad', sid)
        self.assertEqual((result['case_status'], result['calls'], result['evidence']),
                         ('NEEDS_INPUT', 0, []))
        self.assertNotIn('command_proposal', result)

    def test_coverage_graph_and_http_commands_are_separate(self):
        report = coverage_report()
        self.assertEqual(report['summary']['total'], 120)
        self.assertEqual(report['summary']['levels']['simulation_verified'], 101)
        self.assertEqual(set(report['igate_simulated']), set(self.profile.igate.actions))
        graph = skill_graph(replay_sim=True)
        graph_edges = {(row['source'], row['target']) for row in graph['edges']}
        self.assertEqual({row['id'] for row in graph['nodes'] if row.get('type') == 'igate_simulated'},
                         set(self.profile.igate.actions))
        for sid in self.profile.igate.actions:
            self.assertIn((sid, igate_data.function_id(sid)), graph_edges)
        self.assertNotIn('IG01', {node['id'] for node in skill_graph()['nodes']})

        def request(path, body):
            raw = json.dumps(body).encode()
            handler = Handler.__new__(Handler)
            handler.path, handler.server = path, SimpleNamespace(server_port=8765)
            handler.headers = {'Content-Type':'application/json', 'Content-Length': str(len(raw)),
                               'Host': 'localhost:8765'}
            handler.rfile, handler.wfile = io.BytesIO(raw), io.BytesIO()
            handler.send_response, handler.send_header, handler.end_headers = Mock(), Mock(), Mock()
            handler.do_POST()
            return handler.send_response.call_args.args[0], json.loads(handler.wfile.getvalue())

        with patch.object(skill_chat, 'CHAT', self.chat):
            status, result = request('/api/chat', {'source_mode': 'replay_sim', 'message': 'Bật Wi-Fi khách'})
            self.assertEqual(status, HTTPStatus.OK)
            envelope = result['command_proposal']['envelope']
            self.assertEqual(envelope['arguments'], {'enabled': True})
            self.assertEqual(request('/api/commands/execute', envelope)[0], HTTPStatus.NOT_FOUND)
            self.assertEqual(request('/api/chat', {'source_mode': 'replay_sim', 'message': 'PING',
                                                   'command_proposal': envelope})[0], HTTPStatus.BAD_REQUEST)
        source = (ROOT / 'gateway_pilot/application/igate_proposal.py').read_text()
        self.assertIsNone(re.search(r'\b(?:ubus|router_display|subprocess|socket|SafeWriteTransaction)\b', source))

    def test_legacy_approval_cannot_launch_new_pack(self):
        old = {key: value for key, value in self.profile.approval.items() if key != 'igate_digest'}
        with self.assertRaisesRegex(PlanError, 'igate_digest_pin'):
            replay_sim.approved_profile(old)
