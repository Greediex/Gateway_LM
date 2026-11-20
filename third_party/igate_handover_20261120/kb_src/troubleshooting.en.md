<!-- doc: troubleshooting.en | topic: troubleshooting | lang: en | as_of: 2026-10-29 | review: draft -->
# Troubleshooting guides that change no configuration

## One slow device — step 1: look at that device's signal
<!-- id: ts.en.slow.s1 | runbook: slow_device | step: s1 | condition: only one device is slow, others are fine | yes: s2 | no: s3 | src: Router_App/router_context_src/kb/src (written from metric_glossary) | aliases: one slow device, slow phone, lag, stutter, slow device | say_for: howto | say: When only one device is slow, first look at its RSSI and link rate; if RSSI is weaker than about −75 dBm, try the device closer to the router. -->
Symptom: one device is slow while the others are fine. Data to read: that device's RSSI and link rate. If RSSI is weaker than about −75 dBm or its link rate is far below the other devices, go to step 2. If the signal is fine, go to step 3. This is a check, not a diagnosis of the cause.

## One slow device — step 2: try closer to the router
<!-- id: ts.en.slow.s2 | runbook: slow_device | step: s2 | condition: the device's signal is weak | yes: s4 | no: s3 | src: Router_App/router_context_src/kb/src | aliases: move closer, move the device, weak signal | say_for: howto | say: Move the device closer to the router or away from obstacles, use it for a few minutes, then check whether the signal is stronger and the slowness is gone. -->
Move the device closer to the router (or away from obstacles such as walls and metal cabinets) and use it for a few minutes. Check again: is RSSI stronger and is the slowness reduced? If it clearly improves, placement matters; an extra access point may be worth considering. If not, go to step 3. A better signal after moving is a before/after observation, not proof of the only cause.

## One slow device — step 3: check the device itself
<!-- id: ts.en.slow.s3 | runbook: slow_device | step: s3 | condition: the signal is fine or moving did not help | yes: s4 | no: s4 | src: Router_App/router_context_src/kb/src | aliases: check the phone, toggle wifi on the device, update the app | say_for: howto | say: On the device, turn its Wi-Fi off and on, close apps downloading in the background and try another app; if only one app is slow, that service may be the cause. -->
On the device: turn its Wi-Fi off and on, close apps downloading in the background, try another app or site. If only one app is slow while others are fine, the problem may be that service rather than the home network. This step changes nothing on the router.

## One slow device — step 4: when to ask for help
<!-- id: ts.en.slow.s4 | runbook: slow_device | step: s4 | escalate: 1 | src: Router_App/router_context_src/kb/src | aliases: call support, helpdesk, technician | say_for: howto | say: If it stays slow after these steps, contact support with the device name, when it was slow and what you tried; do not reset the router yourself. -->
If the device stays slow after these steps, contact support with: the device name, when it was slow, what you tried and what happened. Do not reset the router unless told to, because that erases its configuration.

## Several devices lose Internet — step 1: check the WAN status
<!-- id: ts.en.offline.s1 | runbook: all_offline | step: s1 | condition: several devices cannot reach the Internet | yes: s2 | no: s3 | src: Router_App/router_context_src/kb/src | aliases: no internet, internet down, whole house offline, outage, offline | say_for: howto | say: When several devices lose the Internet, first check the WAN: if it is down, check the cables and lights; if it is up but the Internet fails, the fault may be the provider's. -->
Symptom: several devices cannot reach the Internet at the same time. Data to read: the router's WAN and Internet status and how fresh the data is. If the WAN is down, go to step 2. If the WAN is up but the Internet fails, go to step 3. If the data is old, nothing can be concluded yet; fresh data comes first.

## Several devices lose Internet — step 2: check cables and lights
<!-- id: ts.en.offline.s2 | runbook: all_offline | step: s2 | condition: WAN down | yes: s4 | no: s4 | src: Router_App/router_context_src/kb/src | aliases: network cable, fibre, router lights, los light | say_for: howto | say: Check that the cable from the provider's box to the router's WAN port is firmly plugged in and whether the box shows an error light, then wait a few minutes. -->
Check that the cable from the provider's box (modem/ONT) to the router's WAN port is firmly plugged in, and whether the provider box shows an error light (for example red). Do not unplug the fibre unless told to. After reseating the cable, wait a few minutes and check whether the WAN is up.

## Several devices lose Internet — step 3: WAN up but no Internet
<!-- id: ts.en.offline.s3 | runbook: all_offline | step: s3 | condition: WAN up but Internet failing | yes: s4 | no: s4 | src: Router_App/router_context_src/kb/src | aliases: connected but no internet, dns error, cannot open sites | say_for: howto | say: When the WAN is up but the Internet is unreachable, the fault may be on the provider side or in DNS; try several sites on two devices. -->
When the WAN port is connected but the Internet is unreachable, the fault may be on the provider side or in name resolution (DNS). Try opening several different sites on two devices. The router does not test DNS itself, so its configuration alone cannot show whether DNS is broken or working. If it still fails, go to step 4.

## Several devices lose Internet — step 4: report to the provider
<!-- id: ts.en.offline.s4 | runbook: all_offline | step: s4 | escalate: 1 | src: Router_App/router_context_src/kb/src | aliases: call the provider, isp support, helpdesk | say_for: howto | say: Tell the provider when it started, whether the WAN is up or down, the lights on their box and the steps you tried. -->
Contact the provider with: when it started, whether the WAN is up or down, the lights on the provider box, and the steps tried. One good or bad ping to one target is not enough to conclude the fault is the provider's; describe what was actually observed.

## Unstable Wi-Fi — step 1: one device or many
<!-- id: ts.en.flaky.s1 | runbook: wifi_flaky | step: s1 | condition: Wi-Fi keeps dropping | yes: s2 | no: s3 | src: Router_App/router_context_src/kb/src | aliases: unstable wifi, keeps dropping, wifi disconnects, flaky | say_for: howto | say: When the Wi-Fi keeps dropping, first find out whether it is one device or several at once. -->
Symptom: the Wi-Fi connection keeps dropping. First decide: is it one device (step 2) or several at once (step 3)? The router only sees changes between samples, so the number of drops it reports can be too low; it is an observed count, not a complete one.

## Unstable Wi-Fi — step 2: one device
<!-- id: ts.en.flaky.s2 | runbook: wifi_flaky | step: s2 | condition: only one device drops | yes: s4 | no: s4 | src: Router_App/router_context_src/kb/src | aliases: one device drops, forget network, reconnect | say_for: howto | say: If only one device drops, look at its RSSI and SNR, try it closer to the router, or forget the network and reconnect. -->
Look at that device's RSSI and SNR. If the signal is weak, try using it closer to the router. On the device you can "forget" the network and reconnect with the right password. Note the times it drops to compare with the router's history.

## Unstable Wi-Fi — step 3: several devices
<!-- id: ts.en.flaky.s3 | runbook: wifi_flaky | step: s3 | condition: several devices drop | yes: s4 | no: s4 | src: Router_App/router_context_src/kb/src | aliases: many devices drop, interference, wifi channel | say_for: howto | say: If many devices drop at the same moment, note that time and look at how many devices are on each band. -->
Look at the noise level of each band and how many devices are on each. If many devices drop at the same moment, note that time. The router does not currently measure channel utilisation or retransmissions, so it cannot confirm that a neighbour's interference is the cause.

## Unstable Wi-Fi — step 4: when to ask for help
<!-- id: ts.en.flaky.s4 | runbook: wifi_flaky | step: s4 | escalate: 1 | src: Router_App/router_context_src/kb/src | aliases: support, technician | say_for: howto | say: If the drops continue, contact support with the times, which devices and what you tried; do not change the channel or reset the router yourself. -->
If the drops continue, contact support with: the times it dropped, which devices, and what you tried. Do not change the channel or reset the router unless told to.

## Guest network — step 1: is the guest network on
<!-- id: ts.en.guest.s1 | runbook: guest_network | step: s1 | condition: a guest cannot join the guest network | yes: s2 | no: s3 | src: docs/router_snapshot_yaml.md §6 (network guest) | aliases: guest network, guest wifi, guest, visitor cannot connect | say_for: howto | say: First check whether the guest network is on; if it is off, the owner can turn it on on the router's screen. -->
Data to read: which SSID is the guest network (the one whose network is guest) and whether it is on or off. If it is on, go to step 2. If it is off, the owner can turn it on in the app or on the router's screen (step 3). The guest password is not read out from shared data; use a QR code or the channel the owner allows.

## Guest network — step 2: check on the guest's side
<!-- id: ts.en.guest.s2 | runbook: guest_network | step: s2 | condition: the guest network is on | yes: s3 | no: s3 | src: Router_App/router_context_src/kb/src | aliases: enter password, scan qr code, join guest network | say_for: howto | say: Ask the guest to pick the right guest network name, re-enter the password or scan the owner's QR code, and try near the router. -->
Ask the guest to pick the right guest network name, re-enter the password (or scan the owner's QR code) and try near the router. An old device that does not support the network's security type may fail to join; do not lower the security level to work around it.

## Guest network — step 3: the owner decides
<!-- id: ts.en.guest.s3 | runbook: guest_network | step: s3 | escalate: 1 | src: Router_App/router_context_src/kb/src | aliases: owner, turn on guest network | say_for: - | say: Turning the guest network on or off or changing its password is the owner's action and needs confirmation; the assistant only explains. -->
Turning the guest network on or off, or changing its password, is the owner's action and needs confirmation. The assistant only explains; it does not turn on the guest network or send a password to anyone by itself.
