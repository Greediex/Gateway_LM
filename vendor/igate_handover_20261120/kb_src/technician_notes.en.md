<!-- doc: technician_notes.en | topic: technician_notes | lang: en | as_of: 2026-10-29 | review: draft -->
# Reading the router's data feeds (owner and technician scope)

## Feed health flags and what -1 means
<!-- id: tn.en.feed | facts: tn.feed | src: docs/router_snapshot_yaml.md §5 | aliases: feed flags, svc_qos, svc_sec, feed state, -1 -->
The router reports whether the AI QoS and AI Security feeds were readable (qos, security, block: 1 when the source file existed and parsed) and whether those services are on (svc_qos, svc_sec: 1 on, 0 off, -1 the control file did not say). A value of -1 is "not stated", not "off". With the security feed at 0, an empty alert list says the producer is down, nothing about the network.

## Block state per device
<!-- id: tn.en.block | facts: tn.block | src: docs/router_snapshot_yaml.md §5 | aliases: blocked, block file, device blocked -->
A device's block state is "yes" when it is listed in the block file, "no" when the block file exists and does not list it, and "unknown" when there is no block file at all. A change of block state between two samples does not show which request caused it unless a result record links them.

## Snapshot pauses during a speed test and after reboot
<!-- id: tn.en.pause | facts: tn.pause | src: docs/router_snapshot_yaml.md §4 | aliases: speed test pause, frozen counters, reboot, snapshot absent -->
During a speed test the router stops refreshing WAN, system, LAN and client numbers for up to about 25 seconds so its own traffic does not bias the test; security and QoS rows keep updating. After a reboot the snapshot is absent until the first cycle. The timestamp of the snapshot is how a reader notices both; an absent file is never a zero.
