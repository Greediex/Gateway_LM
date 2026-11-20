# Examples

Real turns captured on the reference board on 2026-11-20 with `tools/ask.sh`-style **dry runs**
(`qwen_agent.bench`, `dry_run: true`: nothing was sent to the router). Each file is one line of
`/tmp/qwen-agent/turns.jsonl`, pretty-printed: `input` (the request), `result` (the agent response,
[docs/04_outputs.md](../docs/04_outputs.md) § 1) and `dry_run.would` (what a real request would have done,
§ 4.6). Device names and MAC addresses were replaced by invented ones; everything else is as produced.

| File | Request | `status` | Skill / path | Command | `would` | Time in agent |
|---|---|---|---|---|---|---|
| `read_device_count_vi.json` | có bao nhiêu thiết bị đang kết nối | `ok` | `device.find`, fact rendered by code | `get_info {filter:online}` | `publish` | 4.3 s |
| `read_device_count_en.json` | how many devices are online right now | `ok` | `device.find` | `get_info {filter:online}` | `publish` | 4.2 s |
| `speed_test_run_now.json` | kiểm tra tốc độ mạng | `ok`, `run_now: true` | `router.telemetry`, quick path | `get_info {query:connection_quality}` | `send_run_now` | 0.7 s |
| `write_block_device.json` | chặn mạng iPad của con | `prepared` | `device.block` | `block` device by MAC | `panel_confirm` | 5.0 s |
| `write_guest_wifi_on.json` | bật wifi khách | `prepared` | `network.guest_wifi` | `set_guest_wifi {enabled:true}` | `publish` | 4.8 s |
| `write_prioritize_device.json` | ưu tiên mạng cho laptop của bố | `prepared` | `qos.prioritize` | `optimize {application:GAMING}` (model filled an activity nobody named: see docs/08 § 8.2) | `publish` | 6.5 s |
| `knowledge_cached_answer.json` | wifi 8 là gì | `ok` | `llm_answer_kb`, curated answer (`kb_cache`) | none | `publish` | 1.4 s |
| `out_of_scope_answer.json` | what is the weather today | `ok` | `llm_answer_kb`, model answer from evidence | none | `publish` | 13.4 s |
| `ui_set_language.json` | chuyển giao diện sang tiếng Anh | `prepared` | `ui.set_language` | `set_language {language:en}` | `publish` | 3.2 s |

`requests.txt` lists the same sentences (`lang|text`) for re-running them after a change
([docs/07_source_and_rebuild.md](../docs/07_source_and_rebuild.md) § 7.5):

```sh
while IFS='|' read -r l t; do sh tools/ask.sh -l "$l" "$t"; echo; done < examples/requests.txt
```

`router_snapshot.example.yaml` is an invented router-state file in the format of
[docs/03_inputs.md](../docs/03_inputs.md) § 3.8 (for writing or testing a state producer).

Request payloads, for reference:

```json
{"session_id":"stt-3f9c1a","text":"chặn mạng iPad của con","seq":412,"dur_ms":2140,"is_final":true,"ok":true,"lang":"vi"}
{"text":"bật wifi khách","seq":1000123,"source":"web-ui","session_id":"web-abc","is_final":true,"ok":true}
{"text":"wifi 8 là gì","seq":90000001,"source":"cli","session_id":"cli","is_final":true,"ok":true,"confirm":false,"dry_run":true,"lang":"vi"}
```

(`stt.transcript`, `qwen_agent.ask`, `qwen_agent.bench` respectively.)
