# Skill → Function mapping — 120 Skills

**Những Function liệt kê là đề xuất cho replay, không cấp quyền thực thi.**

| Skill | Classification | Direct READ Function | Suggested evidence Function(s) | Multi scope |
|---|---|---|---|---|
| SK01 | LEGACY_DISCOVER_FROM_REPO | — | — | No |
| A02 | PROPOSED_READ_METADATA | expansion.device_inventory | expansion.device_inventory | No |
| A03 | NO_DIRECT_READ_FUNCTION | — | expansion.device_inventory, expansion.identity_consistency | Yes |
| A04 | PROPOSED_READ_METADATA | expansion.device_vendor | expansion.device_vendor | No |
| A05 | NO_DIRECT_READ_FUNCTION | — | expansion.device_inventory, expansion.device_vendor | Yes |
| A06 | PROPOSED_READ_METADATA | expansion.identity_consistency | expansion.identity_consistency | No |
| A07 | NO_DIRECT_READ_FUNCTION | — | expansion.device_inventory, expansion.evidence_history | No |
| A08 | PROPOSED_READ_METADATA | expansion.client_association | expansion.client_association | No |
| SK02 | LEGACY_DISCOVER_FROM_REPO | — | — | No |
| B02 | PROPOSED_READ_METADATA | expansion.radio_health | expansion.radio_health | No |
| B03 | PROPOSED_READ_METADATA | expansion.ssid_config | expansion.ssid_config | No |
| B04 | PROPOSED_READ_METADATA | expansion.wireless_signal | expansion.wireless_signal | No |
| B05 | PROPOSED_READ_METADATA | expansion.airtime_usage | expansion.airtime_usage | No |
| B06 | PROPOSED_READ_METADATA | expansion.rf_environment | expansion.rf_environment | No |
| B07 | PROPOSED_READ_METADATA | expansion.roaming_events | expansion.roaming_events | No |
| B08 | PROPOSED_READ_METADATA | expansion.mesh_backhaul | expansion.mesh_backhaul | No |
| C01 | PROPOSED_READ_METADATA | expansion.ethernet_ports | expansion.ethernet_ports | No |
| C02 | PROPOSED_READ_METADATA | expansion.ethernet_counters | expansion.ethernet_counters | No |
| C03 | PROPOSED_READ_METADATA | expansion.switch_fdb | expansion.switch_fdb | No |
| C04 | PROPOSED_READ_METADATA | expansion.bridge_health | expansion.bridge_health | No |
| C05 | PROPOSED_READ_METADATA | expansion.vlan_membership | expansion.vlan_membership | No |
| C06 | NO_DIRECT_READ_FUNCTION | — | expansion.ethernet_counters, expansion.bridge_health, expansion.stp_status | No |
| C07 | PROPOSED_READ_METADATA | expansion.stp_status | expansion.stp_status | No |
| C08 | PROPOSED_READ_METADATA | expansion.mtu_status | expansion.mtu_status | No |
| SK03 | LEGACY_DISCOVER_FROM_REPO | — | — | No |
| D02 | PROPOSED_READ_METADATA | expansion.dhcp_pool | expansion.dhcp_pool | No |
| D03 | PROPOSED_READ_METADATA | expansion.dhcp_lease_events | expansion.dhcp_lease_events | No |
| D04 | NO_DIRECT_READ_FUNCTION | — | expansion.identity_consistency, expansion.dhcp_lease_events, expansion.neighbor_table | Yes |
| D05 | PROPOSED_READ_METADATA | expansion.neighbor_table | expansion.neighbor_table | No |
| D06 | PROPOSED_READ_METADATA | expansion.ipv6_ra | expansion.ipv6_ra | No |
| D07 | PROPOSED_READ_METADATA | expansion.dhcpv6 | expansion.dhcpv6 | No |
| D08 | NO_DIRECT_READ_FUNCTION | — | expansion.ipv6_ra, expansion.wan_routes, expansion.dhcp_pool | No |
| SK04 | LEGACY_DISCOVER_FROM_REPO | — | — | No |
| E02 | PROPOSED_READ_METADATA | expansion.wan_link | expansion.wan_link | No |
| E03 | PROPOSED_READ_METADATA | expansion.wan_routes | expansion.wan_routes | No |
| E04 | PROPOSED_READ_METADATA | expansion.wan_access | expansion.wan_access | No |
| E05 | PROPOSED_READ_METADATA | expansion.nat_state | expansion.nat_state | No |
| E06 | PROPOSED_READ_METADATA | expansion.multiwan_state | expansion.multiwan_state | No |
| E07 | PROPOSED_READ_METADATA | expansion.wan_events | expansion.wan_events | No |
| E08 | PROPOSED_READ_METADATA | expansion.upstream_probe | expansion.upstream_probe | No |
| SK05 | LEGACY_DISCOVER_FROM_REPO | — | — | No |
| F02 | PROPOSED_READ_METADATA | expansion.dns_resolvers | expansion.dns_resolvers | No |
| F03 | PROPOSED_READ_METADATA | expansion.dns_cache | expansion.dns_cache | No |
| F04 | PROPOSED_READ_METADATA | expansion.split_dns | expansion.split_dns | No |
| F05 | PROPOSED_READ_METADATA | expansion.dhcp_dns | expansion.dhcp_dns | No |
| F06 | PROPOSED_READ_METADATA | expansion.dnssec | expansion.dnssec | No |
| F07 | PROPOSED_READ_METADATA | expansion.encrypted_dns | expansion.encrypted_dns | No |
| F08 | PROPOSED_READ_METADATA | expansion.ntp_sync | expansion.ntp_sync | No |
| G01 | PROPOSED_READ_METADATA | expansion.latency_loss | expansion.latency_loss | No |
| G02 | PROPOSED_READ_METADATA | expansion.network_jitter | expansion.network_jitter | No |
| G03 | NO_DIRECT_READ_FUNCTION | — | expansion.traffic_counters, expansion.bandwidth_usage | No |
| G04 | PROPOSED_READ_METADATA | expansion.traffic_counters | expansion.traffic_counters | No |
| G05 | PROPOSED_READ_METADATA | expansion.bandwidth_usage | expansion.bandwidth_usage | No |
| G06 | PROPOSED_READ_METADATA | expansion.queue_delay | expansion.queue_delay | No |
| G07 | PROPOSED_READ_METADATA | expansion.qos_policy | expansion.qos_policy | No |
| G08 | NO_DIRECT_READ_FUNCTION | — | expansion.latency_loss, expansion.bandwidth_usage, expansion.queue_delay, expansion.wan_events | No |
| SK08 | LEGACY_DISCOVER_FROM_REPO | — | — | No |
| H02 | PROPOSED_READ_METADATA | expansion.services_health | expansion.services_health | No |
| H03 | PROPOSED_READ_METADATA | expansion.storage_health | expansion.storage_health | No |
| H04 | PROPOSED_READ_METADATA | expansion.system_events | expansion.system_events | No |
| H05 | PROPOSED_READ_METADATA | expansion.temperature | expansion.temperature | No |
| H06 | PROPOSED_READ_METADATA | expansion.driver_status | expansion.driver_status | No |
| H07 | PROPOSED_READ_METADATA | expansion.reboot_events | expansion.reboot_events | No |
| H08 | PROPOSED_READ_METADATA | expansion.firmware_info | expansion.firmware_info | No |
| I01 | PROPOSED_READ_METADATA | expansion.firewall_audit | expansion.firewall_audit | No |
| I02 | PROPOSED_READ_METADATA | expansion.exposed_services | expansion.exposed_services | No |
| I03 | PROPOSED_READ_METADATA | expansion.guest_isolation | expansion.guest_isolation | No |
| I04 | PROPOSED_READ_METADATA | expansion.wifi_security | expansion.wifi_security | No |
| I05 | PROPOSED_READ_METADATA | expansion.admin_access | expansion.admin_access | No |
| I06 | PROPOSED_READ_METADATA | expansion.vlan_segmentation | expansion.vlan_segmentation | No |
| I07 | NO_DIRECT_READ_FUNCTION | — | expansion.device_inventory, expansion.exposed_services, expansion.evidence_history | No |
| I08 | PROPOSED_READ_METADATA | expansion.config_compliance | expansion.config_compliance | No |
| J01 | PROPOSED_READ_METADATA | expansion.vpn_tunnel | expansion.vpn_tunnel | No |
| J02 | PROPOSED_READ_METADATA | expansion.vpn_routes | expansion.vpn_routes | No |
| J03 | NO_DIRECT_READ_FUNCTION | — | expansion.vpn_routes, expansion.dns_resolvers, expansion.encrypted_dns | No |
| J04 | PROPOSED_READ_METADATA | expansion.vpn_peers | expansion.vpn_peers | No |
| J05 | NO_DIRECT_READ_FUNCTION | — | expansion.vpn_tunnel, expansion.vpn_routes, expansion.vpn_peers | No |
| J06 | PROPOSED_READ_METADATA | expansion.vpn_ipv6 | expansion.vpn_ipv6 | No |
| J07 | PROPOSED_READ_METADATA | expansion.policy_routes | expansion.policy_routes | No |
| J08 | PROPOSED_READ_METADATA | expansion.remote_access | expansion.remote_access | No |
| K01 | PROPOSED_READ_METADATA | expansion.evidence_history | expansion.evidence_history | No |
| K02 | NO_DIRECT_READ_FUNCTION | — | expansion.evidence_history, expansion.incident_events, expansion.wan_events | No |
| K03 | NO_DIRECT_READ_FUNCTION | — | expansion.evidence_history, expansion.incident_events, expansion.latency_loss | No |
| K04 | NO_DIRECT_READ_FUNCTION | — | expansion.incident_events, expansion.evidence_history | No |
| K05 | PROPOSED_READ_METADATA | expansion.incident_events | expansion.incident_events | No |
| K06 | NO_DIRECT_READ_FUNCTION | — | expansion.evidence_history, expansion.wan_events, expansion.upstream_probe | No |
| K07 | NO_DIRECT_READ_FUNCTION | — | expansion.evidence_history, expansion.upstream_probe, expansion.latency_loss | No |
| K08 | NO_DIRECT_READ_FUNCTION | — | expansion.evidence_history | No |
| L01 | PROPOSED_READ_METADATA | expansion.topology_inventory | expansion.topology_inventory | No |
| L02 | PROPOSED_READ_METADATA | expansion.topology_associations | expansion.topology_associations | No |
| L03 | PROPOSED_READ_METADATA | expansion.gateway_links | expansion.gateway_links | No |
| L04 | NO_DIRECT_READ_FUNCTION | — | expansion.topology_inventory, expansion.topology_associations, expansion.gateway_links | No |
| L05 | PROPOSED_READ_METADATA | expansion.subnet_inventory | expansion.subnet_inventory | No |
| L06 | NO_DIRECT_READ_FUNCTION | — | expansion.topology_inventory, expansion.services_health, expansion.wan_events | No |
| L07 | NO_DIRECT_READ_FUNCTION | — | expansion.gateway_links, expansion.wan_events, expansion.upstream_probe | No |
| L08 | NO_DIRECT_READ_FUNCTION | — | expansion.topology_inventory, expansion.topology_associations, expansion.wan_events, expansion.incident_events | No |
| SK09 | LEGACY_DISCOVER_FROM_REPO | — | — | No |
| M02 | NO_DIRECT_READ_FUNCTION | — | expansion.upstream_probe, expansion.latency_loss, expansion.dns_resolvers, expansion.evidence_history | No |
| M03 | NO_DIRECT_READ_FUNCTION | — | expansion.topology_inventory, expansion.upstream_probe, expansion.evidence_history | No |
| M04 | NO_DIRECT_READ_FUNCTION | — | expansion.upstream_probe, expansion.radio_health, expansion.latency_loss, expansion.dns_resolvers | No |
| M05 | NO_DIRECT_READ_FUNCTION | — | expansion.evidence_history, expansion.upstream_probe, expansion.latency_loss | No |
| M06 | NO_DIRECT_READ_FUNCTION | — | expansion.upstream_probe, expansion.radio_health, expansion.dns_resolvers, expansion.latency_loss | No |
| M07 | NO_DIRECT_READ_FUNCTION | — | expansion.topology_associations, expansion.incident_events, expansion.evidence_history | No |
| M08 | NO_DIRECT_READ_FUNCTION | — | expansion.incident_events, expansion.evidence_history | No |
| SK13 | LEGACY_DISCOVER_FROM_REPO | — | — | No |
| N02 | NO_DIRECT_READ_FUNCTION | — | expansion.config_snapshot, expansion.config_drift, expansion.firewall_audit | No |
| N03 | PROPOSED_READ_METADATA | expansion.config_snapshot | expansion.config_snapshot | No |
| N04 | PROPOSED_READ_METADATA | expansion.config_drift | expansion.config_drift | No |
| N05 | NO_DIRECT_READ_FUNCTION | — | expansion.config_snapshot | No |
| N06 | NO_DIRECT_READ_FUNCTION | — | expansion.config_snapshot, expansion.config_drift, expansion.firewall_audit | No |
| N07 | PROPOSED_READ_METADATA | expansion.rollback_readback | expansion.rollback_readback | No |
| N08 | NO_DIRECT_READ_FUNCTION | — | expansion.config_snapshot, expansion.incident_events | No |
| O01 | NO_DIRECT_READ_FUNCTION | — | expansion.client_association, expansion.radio_health, expansion.dhcp_lease_events, expansion.upstream_probe, expansion.dns_resolvers | Yes |
| O02 | NO_DIRECT_READ_FUNCTION | — | expansion.radio_health, expansion.wireless_signal, expansion.airtime_usage, expansion.latency_loss, expansion.bandwidth_usage, expansion.queue_delay | Yes |
| O03 | NO_DIRECT_READ_FUNCTION | — | expansion.wan_events, expansion.roaming_events, expansion.latency_loss, expansion.evidence_history | Yes |
| O04 | NO_DIRECT_READ_FUNCTION | — | expansion.dns_resolvers, expansion.dns_cache, expansion.split_dns, expansion.dhcp_lease_events | No |
| O05 | NO_DIRECT_READ_FUNCTION | — | expansion.client_association, expansion.radio_health, expansion.guest_isolation, expansion.dhcp_lease_events | Yes |
| O06 | NO_DIRECT_READ_FUNCTION | — | expansion.latency_loss, expansion.network_jitter, expansion.bandwidth_usage, expansion.queue_delay, expansion.wireless_signal | Yes |
| O07 | NO_DIRECT_READ_FUNCTION | — | expansion.wan_link, expansion.wan_routes, expansion.wan_events, expansion.upstream_probe, expansion.incident_events | No |
| O08 | NO_DIRECT_READ_FUNCTION | — | expansion.device_inventory, expansion.client_association, expansion.topology_associations, expansion.incident_events, expansion.wan_events | Yes |
