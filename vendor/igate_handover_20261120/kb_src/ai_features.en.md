<!-- doc: ai_features.en | topic: ai_features | lang: en | as_of: 2026-11-08 | review: draft -->
# The router's AI features

## What AI QoS is
<!-- id: ai.en.qos | facts: ai.qos | src: esp32/main/ui/ui_showcase_slides.c (AI QoS page); docs/sec_qos_contract.md | aliases: what is ai qos, what is qos, smart priority, app recognition, quality of service, how does the router know who is gaming | say_for: define | say: AI QoS recognises whether each device is gaming, on a video or voice call or streaming video, and puts the right device first when the network is busy. -->
AI QoS recognises what each device is doing, gaming, a video call, a voice call, video streaming or something else, and puts the right device first when the network is busy so calls and games stay smooth. The router also records how long each device spends on each type: now, today and over 7 days. The recognition is done by AI and can mistake an app's type; the router looks at the kind of traffic, it does not read what you watch.

## What AI Security is
<!-- id: ai.en.security | facts: ai.security | src: esp32/main/ui/ui_showcase_slides.c (AI Security pages); docs/ai_security_events.md | aliases: what is ai security, smart security, router detects attacks, anti hacking, network security, protect devices | say_for: define | say: AI Security watches every device on the network on the router itself, spotting infected cameras, port scans, intrusions, attacks and new devices. -->
AI Security watches every device on the network, day and night, on the router itself: infected cameras, port scans, intrusions, attacks and new devices as they join. Every event is named and given a severity, and the device can be blocked with one tap or one sentence. Statistics cover 24 hours or 7 days.

## AI on the router in five steps
<!-- id: ai.en.pipeline | facts: ai.pipeline | src: esp32/main/ui/ui_showcase_slides.c (pipeline page) | aliases: how does the ai work, what does the ai in the router do, ai pipeline, processing network data, how does edge ai work | say_for: define | say: The router's AI works in five steps: see every device, classify the traffic, decide who goes first or is blocked, apply it on the router, and give a smoother experience. -->
The router's AI goes from raw traffic to a better experience in five steps: see every device and flow on the network; classify calls, games and video and spot attacks; decide who goes first and what is blocked; apply it on the router in real time; the result is smooth calls and games and a protected home. All of it is processed on the device: fast, private, and it keeps working offline.

## How iGate understands and answers
<!-- id: ai.en.llm | facts: ai.llm | src: llm/core/README.md (Pipeline); llm/docs/qwen35_tong_hop_20261107.md §1 | aliases: how does igate work, language model, llm, chatgpt, where do the answers come from, does igate make things up, which model, artificial intelligence | say_for: define | say: iGate uses a language model running on the router, takes the router's real data or the built-in guides and answers briefly; without data it says so. -->
iGate uses a language model (LLM) running on the router's AI processor, with no cloud call. For each request it works out whether you are asking or giving a command, takes the router's real data (devices, signal, traffic, measurements) or the built-in guides, and answers briefly. Without data it says so instead of guessing. Commands that change the network are safety-checked and wait for your confirmation. Each request usually takes a few seconds.

## Wi-Fi Sensing notices movement
<!-- id: ai.en.sensing | facts: ai.sensing | src: docs/wifi_sensing_preview.md §1-3 | aliases: what is wifi sensing, sensing with wifi, presence detection, elderly care, fall detection, no camera | say_for: define | say: Wi-Fi Sensing uses the Wi-Fi signal to notice movement at home, with no camera; on the current router it is a preview with simulated data. -->
Wi-Fi Sensing uses the Wi-Fi signal itself to notice movement at home, with no camera or wearable, aimed at caring for older family members (daily activity, whether someone is there, a reminder after long inactivity). On the current router it is a preview with simulated data; the router does not measure it for real yet and never identifies who someone is.

## Where the AI's data stays
<!-- id: ai.en.data | facts: ai.data | src: esp32/main/ui/ui_showcase_slides.c (pipeline page); docs/router_snapshot_yaml.md §2 | aliases: is my data sent anywhere, does the ai collect data, privacy, where is data stored, does it know what i watch | say_for: define,judge | say: The AI's data is processed on the router and not sent to the cloud; the router knows each device's kind of activity, not what you watch. -->
The AI features process data on the router: traffic types, usage time, security events and speech are not sent to the cloud for analysis. The router knows each device's kind of activity (for example streaming video), not the specific page or video. Traffic and usage statistics are kept for about 7 days for the charts.
