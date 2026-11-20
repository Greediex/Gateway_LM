<!-- doc: metric_glossary.en | topic: metric_glossary | lang: en | as_of: 2026-10-29 | review: draft -->
# What the router's numbers mean

## RSSI — Wi-Fi signal strength
<!-- id: mg.en.rssi | facts: mg.rssi | src: docs/router_snapshot_yaml.md §3 (clients.rssi_dbm) | aliases: rssi, signal strength, signal level, dBm, what rssi means, explain rssi, rssi meaning | say_for: define | say: RSSI is the Wi-Fi signal level the router receives from a device, in dBm and always negative: closer to 0 is stronger. -->
RSSI is the Wi-Fi signal level the router receives from a device, in dBm, always negative: closer to 0 is stronger (−50 dBm is stronger than −75 dBm). What it measures: the radio link between that device and the router at the moment of the sample. What it does not prove: a weak RSSI alone does not show that it caused a video to stutter or the network to feel slow; link rate, noise and other devices also matter. Wired devices have no RSSI.

## SNR — signal-to-noise ratio
<!-- id: mg.en.snr | facts: mg.snr | src: docs/router_snapshot_yaml.md §3 (clients.snr_db) | aliases: snr, signal to noise, noise, interference | say_for: define | say: SNR is the gap between a device's signal and the background noise, in dB; higher means a cleaner link. -->
SNR is the gap between a device's signal and the background noise, in dB; higher means a cleaner link. With the same RSSI but more noise, SNR drops and the connection is more likely to be unstable. What it measures: radio quality at the router. What it does not tell: where the noise comes from (which device or neighbouring network), because the router does not report that.

## Link rate is not Internet speed
<!-- id: mg.en.link | facts: mg.link | src: docs/router_snapshot_yaml.md §6 | aliases: link rate, phy rate, link speed, link_mbps, connection speed, shows high mbps but downloads slowly, link speed higher than internet speed | say_for: define,compare | say: Link rate is the physical rate a device and the router negotiate over the air or cable; it is not the Internet speed. -->
Link rate is the physical rate a device and the router negotiate over the air or cable, in Mbit/s. It tells how fast the hop between the device and the router could go under current conditions; it is not the speed actually achieved and not the Internet speed. The figure a device shows in its Wi-Fi details, such as 866, 1200, 2400 or 5760 Mbps, is the link rate; real downloads usually reach only part of it. Internet speed is also limited by the plan, the WAN line and the far-end server. Units matter: Mbit/s (megabits) is not MB/s (megabytes); 8 Mbit/s is about 1 MB/s.

## Throughput in use
<!-- id: mg.en.throughput | facts: mg.throughput | src: docs/router_snapshot_yaml.md §6 (rx_mbps/tx_mbps) | aliases: throughput, traffic, rx, tx, download, upload, bandwidth in use | say_for: define | say: Throughput is the data that actually passed in the last few seconds; a low number may only mean nobody was downloading much, not how fast the network can go. -->
Throughput is the data that actually passed in the last few seconds, in Mbit/s, computed from the router's byte counters: rx is received and tx is sent, as seen from the router. A low number may only mean nobody was downloading much at that moment; it does not measure how fast the network can go. Maximum speed needs a separate speed test, which the router does not run to answer a question.

## Ping to one target
<!-- id: mg.en.ping | facts: mg.ping | src: docs/router_snapshot_yaml.md §3 (wan.ping_ms) | aliases: ping, latency, delay, ms, ping vs jitter, difference between ping and jitter | say_for: define | say: Ping is the round-trip time of a packet to one target server, in milliseconds; the router measures only one target it chose. -->
Ping is the round-trip time of a packet to one target server, in milliseconds. The router measures only one target it chose, so a good ping means the path to that target is good; it does not prove every service (games, video, banking) is fine. Jitter is measured only by the speed test; the router does not measure packet loss. Without a measurement the answer is "unknown", never zero.

## WAN and Internet status
<!-- id: mg.en.wan | facts: mg.wan | src: docs/router_snapshot_yaml.md §3 (wan.up, wan.internet) | aliases: wan, internet, outage, offline, provider connection, up, down | say_for: define,compare | say: The WAN is the port that connects the router to the provider; the WAN can be up while the Internet still fails. -->
The WAN is the port that connects the router to the provider. "WAN up" means the port has a connection; "internet" means the router could check a path to the Internet. They differ: the WAN can be up while the Internet still fails (for example a provider-side or DNS fault). The DNS servers configured on the router are only addresses that were set; they do not prove name resolution is working.

## Router CPU, RAM and temperature
<!-- id: mg.en.system | facts: mg.cpu, mg.ram, mg.temp | src: docs/router_snapshot_yaml.md §3 (sys) | aliases: cpu, ram, memory, temperature, system load, load | say_for: define | say: CPU is how busy the processor is, RAM the share of memory in use, and temperature comes from the board's sensor; high values matter when they last several minutes. -->
CPU (%) is how busy the processor is, RAM (%) the share of memory in use, and temperature (°C) comes from the board's sensor when it has one. A brief high reading is normal; it matters when it stays high for several minutes. When the board has no temperature sensor the router reports none, and the answer must say there is no data rather than guess. A reference threshold is not a shutdown policy.

## How fresh the data is
<!-- id: mg.en.freshness | facts: mg.freshness | src: docs/router_snapshot_yaml.md §4 | aliases: stale, old data, fresh, updated, data age | say_for: define | say: The router writes its state about every 2 seconds; when a record is old, the answer must say the data is old. -->
The router writes its state about every 2 seconds. Each answer is based on a record with its own age; when that record is old (for example during a speed test some numbers pause, or right after a reboot) the answer must say the data is old. Part of the data can be fresh while another part is old, so the time of the whole file does not make every number newly measured.

## QoS class and usage time
<!-- id: mg.en.qos | facts: mg.qos | src: docs/router_snapshot_yaml.md §3 (qos_today, qos_7d) | aliases: qos, gaming, streaming, usage time, application, GAMING, VSTREAM | say_for: define | say: The router puts devices in traffic classes such as gaming, video, voice and video calls; that is the class a classifier assigned, not an application's name. -->
The router puts devices in traffic classes such as GAMING, VSTREAM (video), VOICE and VIDEOCALL. That is the class a classifier assigned, not the name of an application; the router does not know which site you are watching. Daily and weekly usage times are estimates. While the router has no valid clock it cannot count "today", so an empty table at that time does not mean nobody used anything.

## An empty security list does not mean safe
<!-- id: mg.en.security | facts: mg.security | src: docs/router_snapshot_yaml.md §5 | aliases: security, alert, attack, safe, threat, feed | say_for: define,judge | say: An empty security list only means nothing was recorded or the data source is off; it does not prove the network is safe. -->
Security alerts come from a separate analysis service. When that service is not running, the alert list is empty, which only means the data source is off, not that the network is safe. An alert does not by itself prove a device was compromised; it says the detector saw a sign according to its own rules.

## What ping is good
<!-- id: mg.en.ping_levels | facts: mg.ping_levels | src: Router_App/router_context_src/kb/src/activity_needs.en.md (an.en.game, an.en.call); grades chosen 2026-11-10 (response-latency plan step 1E, user delegated) | aliases: what ping is good, is my ping high, good latency, is 100 ms ping slow, ping levels, good ping | say_for: judge | say: A ping of 50 ms or less is good; 51 to 100 ms is fair, still fine for games and video calls; 101 to 150 ms is weak and feels laggy; over 150 ms is bad. | judge: ping_ms <=50 good, <=100 fair, <=150 weak, bad -->
Lower ping is better. The router uses four grades: 50 ms or less is good, enough even for online games; 51 to 100 ms fair, still fine for games and video calls; 101 to 150 ms weak, games and calls feel laggy; over 150 ms bad. Ping is measured to one target only, so a good grade does not prove every service is fine.

## What jitter is good
<!-- id: mg.en.jitter_levels | facts: mg.jitter_levels | src: docs/speedtest.md (jitter); grades chosen 2026-11-10 (response-latency plan step 1E, user delegated) | aliases: what jitter is good, is my jitter high, jitter levels, good jitter | say_for: judge | say: A jitter of 10 ms or less is good; 11 to 30 ms is fair; 31 to 50 ms is weak and calls or games may stutter; over 50 ms is bad. | judge: jitter_ms <=10 good, <=30 fair, <=50 weak, bad -->
Jitter is how much the ping varies; only the network quality test measures it, and lower is better. The router uses four grades: 10 ms or less is good; 11 to 30 ms fair; 31 to 50 ms weak, video calls and games may stutter; over 50 ms bad.
