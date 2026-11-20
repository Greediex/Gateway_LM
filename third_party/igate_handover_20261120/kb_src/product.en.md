<!-- doc: product.en | topic: igate_product | lang: en | as_of: 2026-11-08 | review: draft -->
# iGate A86-C — this router

## What the iGate A86-C is
<!-- id: prod.en.what | facts: prod.name, prod.line | src: esp32/main/ui/ui_home_screens.c (About) | aliases: what is this router, router name, which router, router model, product name, igate, igate a86-c, a86c, ai gateway, this gateway | say_for: define | say: The router you are using is the iGate A86-C, a Wi-Fi 8 gateway that is also an edge AI platform; its voice assistant is called iGate. -->
The router you are using is the iGate A86-C, an "Edge AI Platform & Wi-Fi 8 Gateway": a Wi-Fi 8 gateway that is also an edge AI platform. It combines Wi-Fi 8, multi-gig networking and AI that runs on the router itself, for real-time network insight, AI quality-of-experience optimisation and proactive security. Its voice assistant is called iGate; you wake it by saying "Hey iGate".

## Which Wi-Fi standard this router uses
<!-- id: prod.en.wifi | facts: prod.wifi8, prod.bands, prod.phy | src: esp32/main/ui/ui_showcase_slides.c (cover); esp32/main/ui/ui_wifi_compare.c | aliases: which wifi standard, what wifi generation, is it wifi 8, wifi 7 or wifi 8, 802.11bn, tri-band, three bands, top speed, 11.5 gbps | say_for: define | say: The iGate A86-C is a tri-band Wi-Fi 8 (IEEE 802.11bn) router, 2.4 GHz, 5 GHz and 6 GHz, with a maximum Wi-Fi PHY rate of 11.5 Gbps. -->
The iGate A86-C is a tri-band Wi-Fi 8 (IEEE 802.11bn) router: 2.4 GHz, 5 GHz and 6 GHz. Its maximum Wi-Fi PHY rate is 11.5 Gbps; that is the theoretical rate of the radio, not the Internet speed you will measure. Older phones and laptops (Wi-Fi 5, 6, 7) still connect as before; to get every Wi-Fi 8 benefit, the device must support Wi-Fi 8 too.

## Ports and wired speed
<!-- id: prod.en.ports | facts: prod.wan10g, prod.multigig | src: esp32/main/ui/ui_showcase_slides.c (speed test page) | aliases: wan port, 10 gbe, 10 gigabit, multi-gig, ethernet ports, wired speed, 10 gbps plan | say_for: - | say: The router has a 10 GbE WAN port and multi-gig LAN ports, and it measures Internet speed up to 10 Gbps by itself. -->
The router has a 10 GbE WAN port for the Internet line and multi-gig LAN ports for wired computers, TVs and set-top boxes. It measures Internet speed up to 10 Gbps by itself, no app needed. Real speed is also limited by the service plan, the cables and the device at the other end, not only by the router.

## AI that runs on the router
<!-- id: prod.en.ai | facts: prod.npu, prod.ai_offline | src: esp32/main/ui/ui_showcase_slides.c (cover, pipeline page) | aliases: npu, 10 tops, ai on the router, edge ai, on-device, no cloud, offline ai | say_for: define | say: The router has an AI processor of up to 10 TOPS for AI QoS, AI Security and the voice assistant; all of it runs on the router. -->
The router has an AI processor (NPU) of up to 10 TOPS, used for three things: AI QoS (recognising who is gaming, on a video call or streaming, and putting them first), AI Security (detecting attacks and unknown devices) and the voice assistant. All of it runs on the router: fast, private because the data stays at home, and it keeps working when the Internet is down.

## The iGate voice assistant
<!-- id: prod.en.voice | facts: prod.voice, prod.voice_lang | src: esp32/main/ui/ui_showcase_slides.c (voice page); docs/web_voice_mic.md | aliases: voice assistant, hey igate, talk to the router, voice commands, vietnamese, english, what is igate | say_for: define,ability | say: I am iGate, the router's voice assistant. Say "Hey iGate", then ask or give a command; speech is handled on the router and nothing goes to the cloud. -->
iGate is the router's voice assistant. Say "Hey iGate" or press the talk button, then ask or give a command in Vietnamese or English. Speech is recognised and understood on the router, nothing goes to the cloud. iGate answers from the router's own data and the built-in guides; a command that changes the network always waits for your confirmation before it runs.

## The router's screen and your phone
<!-- id: prod.en.screens | facts: prod.panel, prod.web | src: docs/web_panel_https.md §1; Router_App/router_screen_src/README.md | aliases: touch screen, panel, router screen, use on phone, vnpt.internal, router web page, control from phone | say_for: define,howto | say: The router has its own touch screen; on a phone or computer on the home network, open a browser and type vnpt.internal to use the same screen. -->
The router has its own touch screen for status and controls. The same screen works on a phone or computer on the home network: open a browser and type vnpt.internal, or scan the QR code on the "Use on your phone" card in Settings. The phone shows exactly the router's screen, and a tap on either has the same effect.

## The maker of this router
<!-- id: prod.en.maker | facts: prod.maker | src: esp32/main/ui/ui_home_screens.c (About) | aliases: maker, manufacturer, made by, brand, made in, vnpt qualcomm, excellence center, made in vietnam, which company | say_for: define | say: The iGate A86-C is developed by the VNPT – Qualcomm Excellence Center, part of VNPT Technology, and is designed and made in Vietnam. -->
The iGate A86-C is developed by the VNPT – Qualcomm Excellence Center, part of VNPT Technology, the technology company of VNPT Group. Its hardware is built on Qualcomm Technologies' platform. It is designed and manufactured in Vietnam.

## What the router can do
<!-- id: prod.en.features | facts: prod.features | src: esp32/main/ui/ui_showcase_slides.c (product chapter) | aliases: features, what can the router do, what can you do, functions, what does igate do, capabilities | say_for: ability | say: The router shows the Internet status and devices, runs speed tests, keeps traffic history, has AI QoS, AI Security and a guest network, and can block, limit, prioritise, schedule and label devices. -->
Main features: Internet status and the devices connected; a speed test run by the router itself; traffic history by hour, by day and by service; AI QoS showing who is gaming, on a call or streaming, and putting the right device first; AI Security alerts for attacks and unknown devices; a guest network shared by QR code; block, unblock, speed limits, priority and timers per device; device labels so you can say "mom's phone"; and the iGate voice assistant.

## Features on the roadmap (not yet available)
<!-- id: prod.en.roadmap | facts: prod.roadmap | src: esp32/main/ui/ui_showcase_slides.c (coming soon page) | aliases: coming soon, not yet, roadmap, future, when will, mesh, remote access, time limits for kids | say_for: define,ability | say: Some features are on the roadmap and not available yet: seamless roaming between access points, automatic best channel, remote management and daily time budgets for children. -->
Some features are on the platform's roadmap and the router does not have them yet: seamless roaming between several access points (mesh), automatic best channel and power, suggested fixes before you ask, managing the network from outside the home, daily time budgets for children, and blocking one game while keeping homework apps. Asked about these, iGate says they are not available yet.

## What iGate cannot do yet
<!-- id: prod.en.limits | facts: prod.cannot | src: llm/core/README.md (guards W09, W11); Router_App/router_display_src/LLM_JSON_CMD.md §5.10-5.11 | aliases: cannot do, not supported, restart the router, turn on the lights, smart home, weather, news, search the internet, make a call, conditional command | say_for: ability | say: iGate handles the router's network only; it cannot yet control smart-home devices, restart the router by voice, or give weather or news. -->
iGate handles the router's network only. It cannot yet: control lights, plugs or smart-home devices; restart the router by voice; give weather, news or search the Internet; place calls or make a phone ring; take conditional commands such as "if he is still gaming tonight, block him" (the router does not watch for that condition: give the command when you want it, or name a time to schedule it). For a request outside its abilities, iGate says so instead of guessing.

## What works without the Internet
<!-- id: prod.en.offline | facts: prod.offline | src: llm/docs/demo_capability_inventory_plan_20261107.md (K1); llm/docs/qwen4b_voice_demo_execution_plan_20261104.md §1 | aliases: internet down, no internet, offline, when the internet drops, does it need internet | say_for: define,judge | say: Without the Internet, the router's screen, iGate, the device list, schedules and blocking still work; only the Internet speed test and web access stop. -->
Without the Internet you can still use the router's screen, the iGate voice assistant (speech recognition and AI run on the router), the device list, labels, schedules, blocking and unblocking, and the home Wi-Fi itself. Only what needs the outside Internet stops: the Internet speed test, automatic time zone detection, and of course web access.

## The AI Gateway Platform
<!-- id: prod.en.platform | facts: prod.platform | src: esp32/main/ui/ui_showcase_slides.c (platform chapter) | aliases: ai gateway platform, platform, architecture, sdk, api, centralized management, copilot | say_for: define | say: The iGate A86-C runs on VNPT Technology's AI Gateway Platform, which manages devices, models and AI services and runs AI models on the device. -->
The iGate A86-C runs on VNPT Technology's AI Gateway Platform, one platform from the chip to the AI service: centralised management of devices, models, policies and services at scale; deployment and on-device inference of AI models; intelligence at the edge for QoE, security, IoT and network insight in real time; an SDK/API for fast integration of new services; and built-in security and data protection. The AI assistant (LLM agent) is part of this platform.
