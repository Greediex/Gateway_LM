<!-- doc: voice.en | topic: igate_voice | lang: en | as_of: 2026-11-08 | review: draft -->
# Talking to iGate

## How to start talking
<!-- id: voc.en.start | facts: voc.start | src: docs/web_voice_mic.md; docs/kws_operating_point.md | aliases: how to talk, start talking, wake igate, hey igate, talk button, listening, how do i give a command, how to speak, cancel | say_for: howto | say: Say "Hey iGate" or press the talk button on Home, wait for "Listening", then say one short, clear sentence. -->
Say "Hey iGate" towards the router, or press the talk button on Home, wait for "Listening", then say one short, clear sentence. On a phone, open vnpt.internal: hold the talk button while you speak and release when done. While iGate is thinking the screen spins and shows the current step; tap X to cancel. Give one request at a time.

## What I can say
<!-- id: voc.en.say | facts: voc.say | src: llm/config/skills/catalog.json; docs/voice_command_execution.md §2 | aliases: what can i say, what can you do, what can i ask, example commands, list of commands, how can you help | say_for: ability,howto | say: You can ask about the router and devices, check the network quality, block, limit or prioritise a device, turn on the guest Wi-Fi, set timers, and ask questions such as "What is Wi-Fi 8?". -->
You can ask about the router ("What is the router's CPU?", "Is the Internet up?", "Which bands is the router broadcasting?"); about devices ("How many devices are online?", "How is mom's phone's signal?", "Which devices are gaming?"); measure the network ("Check the network quality"); give commands ("Block the game console", "Limit the TV's download to 5 Mbps", "Prioritise dad's laptop", "Turn on the guest Wi-Fi for 30 minutes"); set timers and list schedules; and ask questions ("What is Wi-Fi 8?", "What is RSSI?", "What does VNPT Technology do?").

## How to block and unblock a device
<!-- id: voc.en.block | facts: voc.block | src: Router_App/router_display_src/LLM_JSON_CMD.md §5.5-5.6; docs/voice_command_execution.md §2 | aliases: how do i block a device, how to block, what should i say to block, block internet, unblock, restore internet, cut off internet | say_for: howto | say: Say the action, then the device, for example "Block the game console" or "Unblock the kid's tablet"; the router blocks only when you tap Confirm. -->
Say the action, then the device: "Block the game console", "Block the kid's phone", "Unblock the kid's tablet" or "Restore the Internet for the living room TV". The name is the one in the device list or a label you gave it. The router's screen asks "Block … ?" and blocks only when you tap Confirm within about 20 seconds. Blocking an app ("block games for …") currently blocks that whole device's Internet, and iGate says so.

## How to limit speed and set priority
<!-- id: voc.en.limit | facts: voc.limit | src: Router_App/router_display_src/LLM_JSON_CMD.md §5.7-5.8 | aliases: speed limit, limit bandwidth, cap the speed, prioritise, priority for gaming, optimise gaming, how to limit | say_for: howto | say: Name the device and the Mbps, for example "Limit the TV's download to 5 Mbps"; for priority say "Prioritise dad's laptop". -->
Limit: name the device and the Mbps, one direction is enough: "Limit the TV's download to 5 Mbps", "Limit the console to 20 Mbps down and 5 Mbps up". The direction you do not name stays as it was. Priority: "Prioritise dad's laptop" or "Prioritise gaming on the console"; the router puts that whole device first when the network is busy and slows nobody when it is idle. Mbps must be a whole number from 1 to 10,000.

## How to set a timer
<!-- id: voc.en.schedule | facts: voc.schedule | src: Router_App/router_display_src/LLM_JSON_CMD.md §5.12 | aliases: timer, schedule, block for 30 minutes, block from 9 pm, every day, weekdays, weekends, cancel a schedule, list schedules | say_for: howto | say: Add the time to the command, for example "Block the kid's tablet for 30 minutes" or "from 9 pm to 6 am"; cancel with "Cancel schedule 3". -->
Add the time to the command: "Block the kid's tablet for 30 minutes" (it goes back as it was afterwards), "Block the game console in 10 minutes", "Block the kid's tablet from 9 pm to 6 am on weekdays" (or every day, weekends), "Turn on the guest Wi-Fi for 2 hours". List them with "List my schedules"; cancel with "Cancel schedule 3". A conditional command such as "if…, then…" cannot be scheduled: name a time instead.

## The guest network by voice
<!-- id: voc.en.guest | facts: voc.guest | src: docs/voice_command_execution.md §2, §4 | aliases: turn on guest wifi, turn off guest wifi, guest network, wifi for visitors, guest wifi password | say_for: howto | say: Say "Turn on the guest Wi-Fi", "Turn on the guest Wi-Fi for 30 minutes" or "Turn off the guest Wi-Fi"; when it is on, the router's screen shows a QR code. -->
"Turn on the guest Wi-Fi", "Turn on the guest Wi-Fi for 30 minutes", "Turn off the guest Wi-Fi". When it is on, the router's screen shows a QR code for guests to scan; with a timer, the guest network turns off on time and the screen shows when. To let a guest join while it is already on, open the Wi-Fi screen to show the QR code. iGate never reads a password aloud.

## Calling devices by name or label
<!-- id: voc.en.names | facts: voc.names | src: docs/device_labels.md §5 | aliases: device name, which device, label, mom's phone, two devices match, device not found, how to name a device | say_for: howto | say: Call a device by its name in the list or by its label, for example "mom's phone" or "living room TV". -->
Call a device by its name in the list ("Galaxy-A54") or by its label: type, owner and room, for example "mom's phone", "living room TV", "An's laptop in the office". If several devices match (mom has two phones), iGate asks which one; if none does, it says it cannot find the device instead of guessing.

## Confirmation and results
<!-- id: voc.en.confirm | facts: voc.confirm | src: docs/voice_command_execution.md §1-2; llm/docs/qwen4b_voice_demo_execution_plan_20261104.md §2b | aliases: confirm, tap confirm, did it work, was it blocked, not successful, no response, why didn't it happen, cancel the command | say_for: define,howto | say: A command that changes the network runs only after you tap Confirm; afterwards the router checks the result and reports Done, Not successful or No response. -->
A command that changes the network never runs before you agree: a block has a Confirm button on the router's screen; other commands have Confirm/Cancel on the assistant page. Without a tap in time, nothing changes. After it runs, the router checks the real result and reports Done, Not successful or No response; it does not report success it has not seen.

## Tips for being understood
<!-- id: voc.en.tips | facts: voc.tips | src: docs/web_voice_mic.md; llm/core/README.md (guards) | aliases: igate does not understand, misheard, tips, how to say it right, too noisy, not heard | say_for: howto | say: One request at a time, short sentences, name the device clearly, and wait for "Listening" before speaking. -->
One request at a time, short sentences, name the device clearly. Wait for "Listening" before speaking. In a noisy room, speak closer to the router or use your phone's microphone through vnpt.internal. If you change your mind mid-sentence ("never mind"), iGate does nothing. A how-to question ("how do I block…") gets instructions, it is not carried out. If a request is unclear, iGate asks back.

## Privacy when talking
<!-- id: voc.en.privacy | facts: voc.privacy | src: esp32/main/ui/ui_showcase_slides.c (voice page); Router_App/router_screen_src/README.md (iGate Portal home) | aliases: is it recording, does it send my voice, privacy, eavesdropping, voice data, who can hear | say_for: define,judge | say: Speech is processed on the router and nothing goes to the cloud; the router listens only after "Hey iGate" or the talk button. -->
Speech is recognised and processed on the router, nothing goes to the cloud. The router listens only after "Hey iGate" or the talk button. The router's screen does not show what you said; the router's web page has an "Ask iGate" column with the last few questions and answers for people viewing on the home network, and that list is gone when the router restarts.
