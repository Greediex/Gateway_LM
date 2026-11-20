<!-- doc: wifi8_intro.en | topic: wifi8_intro | lang: en | as_of: 2026-10-29 | review: draft -->
# Wi-Fi 8 (IEEE 802.11bn, UHR) in plain terms

## What Wi-Fi 8 is
<!-- id: w8.en.what | facts: w8.name, w8.goal | src: docs/wifi8_overview.md §1 | aliases: what is wifi 8, wi-fi 8, wifi8, 802.11bn, UHR, ultra high reliability | say_for: define | say: Wi-Fi 8 is the IEEE 802.11bn standard; it focuses on steady real-world speed, reliability, low latency and staying connected rather than a bigger peak speed. -->
Wi-Fi 8 is the IEEE 802.11bn standard, also called UHR (Ultra High Reliability). Earlier generations were sold on a bigger peak speed; Wi-Fi 8 instead focuses on steady real-world speed, reliability, low latency and staying connected, especially in crowded homes, offices, mesh networks and at the edge of coverage. When the source document was written, 802.11bn was still a draft.

## Wi-Fi 8 compared with Wi-Fi 7
<!-- id: w8.en.vs7 | facts: w8.peak, w8.new | src: docs/wifi8_overview.md §1-2 | aliases: wifi 8 vs wifi 7, difference from wifi 7, wifi 8 max speed, is it faster | say_for: compare | say: Wi-Fi 8's peak rate stays at about 23 Gbps like Wi-Fi 7; what is new is access points that cooperate, seamless roaming, flexible channel use under interference and a long-range mode. -->
Wi-Fi 8's peak rate stays at about 23 Gbps, the same as Wi-Fi 7 (320 MHz channels, 8 streams, 4096-QAM); the source stresses this number is not a sales figure. What is new is elsewhere: coordination between access points (multi-AP), seamless roaming, flexible channel use under interference (NPCA, DSO) and a long-range mode (ELR). So a single download right next to the router should not be expected to be faster than with Wi-Fi 7.

## The three experiences Wi-Fi 8 aims at
<!-- id: w8.en.experience | facts: w8.experiences | src: docs/wifi8_overview.md §1 | aliases: wifi 8 benefits, fast steady, reliable, always connected | say_for: define | say: Wi-Fi 8 aims at three experiences: faster and steadier, more reliable when the network is busy, and always connected while moving. -->
The source groups features into three experiences: Fast — higher and steadier real-world speed, not just the peak; Reliable — fewer stalls and less lag, steadier calls and games when the network is busy; Always-on — wider coverage, longer battery life, no drop-outs while moving.

## Far from the router and the phone's uplink
<!-- id: w8.en.uplink | facts: w8.dru, w8.elr | src: docs/wifi8_overview.md §3.1 | aliases: weak signal far away, far room, DRU, ELR, long range, uplink | say_for: define | say: Far from the router, the router may not hear the phone well; Wi-Fi 8 adds DRU so the device can transmit louder and ELR, a very slow but very far mode. -->
A phone transmits more weakly than the router, so far away the router may no longer hear the phone even though the phone still hears the router. Wi-Fi 8 adds two remedies: DRU spreads the device's signal over a wider slice of spectrum so each part can be sent louder within the legal limit; ELR is a very slow but very far mode that keeps a link alive through walls at only a few Mbit/s. The improvement figures are vendor numbers under favourable conditions.

## When the network is crowded and busy
<!-- id: w8.en.busy | facts: w8.npca, w8.dso, w8.latency | src: docs/wifi8_overview.md §3.2 | aliases: crowded network, many devices, low latency, stable video calls, gaming, NPCA, DSO | say_for: define | say: On a crowded network, NPCA lets a device move to an idle part of the channel and DSO lets the router serve several devices at once, which cuts latency. -->
When a neighbour occupies the main part of a channel, NPCA lets the device move to an idle part instead of waiting silently; DSO lets a wide-channel router serve several narrow-channel devices at once. Priority mechanisms let an urgent packet (a game command, a voice frame) cut ahead of a long transfer and give calls their own lane, reducing latency when the network is busy. The real effect depends on both the router and the device supporting them.

## Access points that cooperate and seamless roaming
<!-- id: w8.en.mesh | facts: w8.mapc, w8.smd | src: docs/wifi8_overview.md §3.3 | aliases: mesh, several routers, multi-AP, roaming, walking around without drops | say_for: define | say: Wi-Fi 8 lets access points cooperate instead of competing, and seamless roaming means fewer breaks while walking around; it needs at least two access points. -->
Today neighbouring access points do not coordinate; they compete for airtime. Wi-Fi 8 introduces multi-AP coordination (MAPC): agreeing on lower power to transmit at the same time, steering signals away from each other's devices, or sharing guaranteed time slots. Seamless roaming (SMD) lets a device join a whole domain of access points, so calls and video break less while walking around. These benefits need at least two access points.

## Examples at home and in a shop
<!-- id: w8.en.examples | facts: w8.home | src: docs/wifi8_overview.md §4 | aliases: home, shop, cafe, small office, real use | say_for: define | say: A multi-storey house with mesh is likely to gain most: far rooms keep a better link and moving between floors drops fewer calls. -->
A multi-storey house with mesh is likely to gain most: far rooms keep a better link and moving between floors drops fewer calls. A busy shop with many devices may find the network calmer at peak times. IoT devices and phones may save battery with the low-power listening mode (DPS). These are capabilities of the standard, not a promise about a particular product.

## Conditions and limits
<!-- id: w8.en.limits | facts: w8.limits, w8.both_ends | src: docs/wifi8_overview.md §4-5 | aliases: wifi 8 limits, conditions, devices must support it, do I need a new phone | say_for: define,judge | say: Most Wi-Fi 8 features need both the router and the device to support them; a Wi-Fi 6/7 phone still works but gets only the router-side benefits. -->
Most features need both ends to support them: a Wi-Fi 8 router with Wi-Fi 6/7 phones still works, but gains only the router-side features. Some features have their own constraints; coordinated beamforming needs routers with many antennas, and seamless roaming needs multi-link devices and a backhaul between access points. Percentages are vendor figures under favourable conditions and should be read as "up to".

## Wi-Fi 8 and the router you are using
<!-- id: w8.en.board | facts: w8.scope, prod.wifi8 | src: esp32/main/ui/ui_showcase_slides.c (cover); docs/wifi8_overview.md | aliases: does this router have wifi 8, is this a wifi 8 router, is wifi 8 on, current router features, igate wifi 8 | say_for: define | say: The router you are using, the iGate A86-C, is a tri-band (2.4/5/6 GHz) Wi-Fi 8 (IEEE 802.11bn) router. -->
The router you are using, the iGate A86-C, is a tri-band (2.4/5/6 GHz) Wi-Fi 8 (IEEE 802.11bn) router. The rest of this guide is general knowledge about the standard: whether a given feature (for example multi-AP coordination) helps you also depends on your devices supporting Wi-Fi 8 and on having several access points. Whether a specific feature is switched on is not inferred from this introduction.
