<!-- doc: manual.en | topic: igate_manual | lang: en | as_of: 2026-11-08 | review: draft -->
# Using the router's screen and web page

## The Home screen
<!-- id: man.en.home | facts: man.home | src: docs/home_screen.md; esp32/main/ui/ui_home.c | aliases: home screen, main screen, network status, what is on the screen, talk button, what can i say | say_for: define | say: The Home screen shows whether the Internet is up, how many devices are connected, the traffic in use and what AI QoS and AI Security are doing. -->
The Home screen shows at once whether the Internet is up, how many devices are connected, the download and upload traffic in use, and what AI QoS and AI Security are doing. It has the button to talk to iGate and "What can I say?" with example phrases. Tap a tile to open its detail screen; the Wi-Fi 8 button opens the Wi-Fi 6·7·8 page.

## Seeing connected devices
<!-- id: man.en.devices | facts: man.devices | src: esp32/main/ui/ui_popup_client_detail.c; docs/device_labels.md §6 | aliases: device list, connected devices, which devices are online, device details, ip address, mac address, signal strength, who is connected, who is connected where | say_for: howto | say: Open "Connected devices" for the list of devices using the network; tap one to see its Wi-Fi band, signal strength, IP and MAC address. -->
Open "Connected devices" for the list of devices using the network. Tap one for its details: Wi-Fi band (2.4, 5 or 6 GHz) or wired, signal strength, IP address, MAC address and its label if it has one. You can also ask iGate, for example "How many devices are online?" or "How is mom's phone's signal?".

## Labelling a device
<!-- id: man.en.labels | facts: man.labels | src: docs/device_labels.md §1, §6 | aliases: label a device, label device, labelling devices, name a device, rename a device, where are device labels, how to label, edit label, delete label, mom's phone | say_for: howto | say: Open a device's details, tap "Label", choose its type, who uses it and the room, then tap Save. -->
Labels let you call devices the way your family talks, for example "mom's phone" or "living room TV". To add one: open a device's details, tap "Label", choose its Type (phone, tablet, laptop, TV, camera, speaker…), Used by (father, mother, grandpa, grandma, child, shared or your own text), Room (living room, bedroom, office, kitchen or your own text), up to 2 other names, then Save. The router shows the phrase you can say to call that device. The device's own name is not changed.

## Managing and deleting labels
<!-- id: man.en.labels_manage | facts: man.labels_manage | src: docs/device_labels.md §1, §6 | aliases: manage labels, delete all labels, offline device labels, labels in settings, how many labels | say_for: howto | say: In Settings, open the "Device labels" card and pick a device to edit or delete its label; the "…" menu has Delete all. -->
In Settings, the "Device labels" card lists every labelled device, offline ones included, filtered by All / Connected / Offline. Pick one to edit or delete its label; the "…" menu has Delete all (confirmed first). Labels are tied to the MAC address and stored on the router, up to 256 devices. A phone using a "private MAC address" can appear as a new device when its MAC changes, and the old label does not follow it.

## Running a speed test
<!-- id: man.en.speedtest | facts: man.speedtest | src: docs/speedtest.md; llm/core/README.md (Network check) | aliases: speed test, test my internet speed, network quality, how fast is my internet, measure speed | say_for: howto | say: Go to Network → "Network quality" and start the test, or say "Check the network quality"; the router measures for about 25 seconds and shows download, upload, ping and jitter. -->
Go to Network → "Network quality" and start the test, or say "Hey iGate, check the network quality". The router measures for about 25 seconds and shows download, upload, ping and jitter. This is the speed of the Internet line to the router, not of the Wi-Fi hop to your phone; a phone far from the router can get less. Ask "What was the speed test result?" to hear the last result.

## Traffic by hour and by service
<!-- id: man.en.traffic | facts: man.traffic | src: docs/traffic_analytics.md §1-2 | aliases: traffic analytics, data usage, how many gb, peak hour, traffic chart, network statistics, 24 hours, 7 days | say_for: howto | say: Open "Traffic analytics" from the traffic tile on Home to see the 24-hour or 7-day chart and traffic by service. -->
"Traffic analytics" (from the traffic tile on Home or from Network) has two tabs. Overview: download and upload over 24 hours or 7 days, with the peak hour or day. Services: download by group, gaming, video streaming, voice calls, video calls and other. The by-service view is an estimate from what each device is doing, not a per-app measurement.

## AI QoS: who is gaming, calling or streaming
<!-- id: man.en.qos | facts: man.qos | src: docs/sec_qos_contract.md; esp32/main/ui/ui_showcase_slides.c (AI QoS page) | aliases: ai qos, who is gaming, who is streaming, priority, gaming time, turn ai qos on off, ai settings, which device is watching video | say_for: howto,define | say: The AI QoS tile on Home shows which devices are gaming, calling or streaming; turn AI QoS on or off in "AI Settings". -->
The AI QoS tile on Home shows which devices are gaming, on a video or voice call, or streaming video, and how long each has done so today or over 7 days. The router uses this to put the right device first when the network is busy. Turn AI QoS and AI Security on or off in "AI Settings". The classification is made by AI and can sometimes mistake an app's type.

## AI Security: alerts and blocking a device
<!-- id: man.en.security | facts: man.security | src: docs/ai_security_events.md §1 | aliases: ai security, security alert, security events, under attack, block a suspicious device, port scan, infected device, where are security alerts, alert screen | say_for: howto | say: The AI Security tile opens a page with Overview, Events and Devices tabs; when there is an alert, the router shows a button to block that device. -->
The AI Security tile opens a page with three tabs: Overview (events, high severity and flagged devices over 24 hours or 7 days), Events (each event with time, device, severity and status) and Devices (attacking, under attack, blocked). When there is an alert, the router shows it with a button to block that device. An empty table only means nothing was recorded; it does not prove the network is completely safe.

## The guest network and sharing by QR code
<!-- id: man.en.guest | facts: man.guest | src: docs/voice_command_execution.md §2, §4; docs/json_command_protocol.md (guest_toggle) | aliases: guest wifi, guest network, turn on guest wifi, share wifi, qr code, guest wifi password, visitors, wifi for guests, how guests connect, connect to the guest wifi, join the guest network | say_for: howto | say: Turn the guest network on or off on the Wi-Fi screen, or say "Turn on the guest Wi-Fi for 30 minutes"; when it is on, the screen shows a QR code for guests. -->
The guest network gives visitors Internet without your main Wi-Fi password. Turn it on or off on the Wi-Fi screen, or say "Turn on the guest Wi-Fi", "Turn on the guest Wi-Fi for 30 minutes", "Turn off the guest Wi-Fi". When it is on, the screen shows a QR code guests scan to join; with a timer, it also shows when it turns off. Turning the guest network on or off reloads Wi-Fi for about 20 seconds, so devices may drop briefly and reconnect.

## Timers and managing schedules
<!-- id: man.en.schedules | facts: man.schedules | src: docs/schedule_settings.md; Router_App/router_display_src/LLM_JSON_CMD.md §5.12 | aliases: timer, schedule, manage schedules, block schedule, see schedules, cancel a schedule, every day, weekdays | say_for: howto | say: Add a time to a command, for example "Block the kid's tablet from 9 pm to 6 am on weekdays"; see schedules in Settings → "Manage schedules", cancel with "Cancel schedule 3". -->
Block, unblock, speed limits, priority and the guest network can be scheduled by voice, for example "Block the kid's tablet from 9 pm to 6 am on weekdays". See the schedules in Settings → "Manage schedules" (count, action, device, time left) or ask "List my schedules"; cancel with "Cancel schedule 3". The router keeps up to 8 schedules at once. Clock-time schedules need the router's clock to be set, and they survive a restart.

## Settings
<!-- id: man.en.settings | facts: man.settings | src: docs/home_screen.md; docs/wallclock_schedules_timezone.md; docs/demo_mode.md | aliases: settings, language, change language, time zone, change the time, demo mode, english, vietnamese | say_for: define,howto | say: Settings has Language, Time zone, Manage schedules, Device labels, Demo mode, AI Settings and the "Use on your phone" card. -->
Settings has: Language (Tiếng Việt / English, for the screen and the web page), Time zone (chosen by hand or detected over the Internet), Manage schedules, Device labels, Demo mode (simulated data for demonstrations), AI Settings (AI QoS and AI Security on/off) and the "Use on your phone" card with a QR code to the router's web page.

## Using it on a phone or computer
<!-- id: man.en.phone | facts: man.phone | src: docs/web_panel_https.md §1; docs/web_voice_mic.md; Router_App/router_screen_src/README.md (Several people) | aliases: use on phone, use the assistant on my phone, vnpt.internal, scan qr, web page, open on computer, talk from phone, phone microphone, several people | say_for: howto | say: On a phone or computer on the home network, open a browser and type vnpt.internal, or scan the QR code in Settings → "Use on your phone". -->
On a phone or computer on the home network, open a browser and type vnpt.internal, or scan the QR code in Settings → "Use on your phone". The page shows the router's screen and works the same way. You can talk through the phone's microphone: hold the talk button and release when done (on a computer, tap to start). Up to 10 screens can watch at once; viewers not in control do not see private details such as passwords.

## Wi-Fi and its bands
<!-- id: man.en.wifi | facts: man.wifi | src: esp32/main/ui_controller/wifi_overview_ctrl.c; docs/json_command_protocol.md §5.3 | aliases: wifi settings, change wifi name, change wifi password, see wifi password, turn off 2.4, wifi bands, ssid, network name | say_for: howto | say: Under Network → Wi-Fi you see each band, its network name and device count; the name and password are changed in "Wi-Fi settings", not by voice. -->
Under Network → Wi-Fi you see each band (2.4 GHz, 5 GHz, 6 GHz), its network name and how many devices use it. The network name and password are changed in "Wi-Fi settings"; a demonstration unit may lock editing. Changing Wi-Fi settings reloads Wi-Fi, so devices may drop briefly and must reconnect with the new password. iGate does not change the Wi-Fi password by voice and never reads a password aloud.

## The Wi-Fi 6 · 7 · 8 page and the Wi-Fi 8 features
<!-- id: man.en.wifi8page | facts: man.wifi8page | src: docs/wifi_generations_compare.md; docs/demo_showcase.md (Wi-Fi 8 chapter) | aliases: wifi 8 page, compare wifi, wifi 8 features, npca, multi-ap, dso, imcs, ldpc, elr, dru, smd, show the illustration | say_for: define,howto | say: The Wi-Fi 8 button on Home opens a comparison of Wi-Fi 6, 7 and 8, with 8 illustrated pages of Wi-Fi 8 features. -->
The Wi-Fi 8 button on Home (or Network → Wi-Fi 6·7·8) opens a comparison of three generations: Wi-Fi 6 for many devices at once, Wi-Fi 7 for speed, Wi-Fi 8 for reliability. Its Features tab has 8 illustrated pages, NPCA, Multi-AP, DSO, iMCS, LDPC, ELR, DRU and SMD, each comparing "Before Wi-Fi 8" with "With Wi-Fi 8". They illustrate principles, not measurements of your home.

## The product tour
<!-- id: man.en.tour | facts: man.tour | src: docs/demo_showcase.md §2-3 | aliases: product tour, introduction, slideshow, show me the product, about the company, about vnpt, introduce the router | say_for: howto | say: Tap the logo on Home for the tour of the router's features, Wi-Fi 8, the AI Gateway Platform and VNPT Technology. -->
Tap the logo on Home for the product tour: the router's features, Wi-Fi 8, the AI Gateway Platform and VNPT Technology. The About screen also has two cards that open the iGate A86-C tour and the company tour. Use ‹ › to change pages and Home to leave; "Try it" opens the real screen of that feature. With Demo mode on, the tour starts by itself after 90 seconds without a touch.

## Demo mode
<!-- id: man.en.demo | facts: man.demo | src: docs/demo_mode.md §1-2 | aliases: demo mode, simulated data, what is demo mode, turn off demo, demo badge, demonstration | say_for: define,howto | say: Demo mode in Settings shows a simulated household of 12 devices for demonstrations; turn it off in Settings to return to real data. -->
Demo mode (in Settings) makes the router show a simulated household of 12 devices, with traffic, AI QoS and AI Security, for demonstrations without a real network. Every screen with numbers carries a DEMO badge, and iGate starts its answers with "Demo data". Commands on simulated devices never touch the real network. Turn Demo mode off in Settings to return to real data.

## Wi-Fi Sensing (preview)
<!-- id: man.en.sensing | facts: man.sensing | src: docs/wifi_sensing_preview.md §1-3 | aliases: wifi sensing, motion sensing, detect movement, elderly care, presence detection, sensing without camera | say_for: define | say: Wi-Fi Sensing uses the Wi-Fi signal to notice movement at home; on this router it is still a preview with simulated data. -->
Wi-Fi Sensing uses the Wi-Fi signal itself to notice movement at home, with no camera or wearable, aimed at caring for older family members. On this router it is a preview: the screen shows what the feature will do, with simulated data when Demo mode is on; it is not a measurement of your home yet.

## The About screen and support
<!-- id: man.en.about | facts: man.about | src: esp32/main/ui/ui_home_screens.c (About) | aliases: about, router information, support contact, where to get help, version | say_for: define,howto | say: The "About" screen gives the router's name, iGate A86-C, its developer, the support web address and a contact QR code. -->
The "About" screen gives the router's name, iGate A86-C, its developer (the VNPT – Qualcomm Excellence Center, part of VNPT Technology), the support web address and a contact QR code, and two cards that open the product tour and the company tour.
