<!-- doc: activity_needs.en | topic: activity_needs | lang: en | as_of: 2026-11-08 | review: draft -->
# How much network each activity needs

## Video and TV streaming
<!-- id: an.en.video | facts: an.video | src: general: common streaming service recommendations | aliases: how many mbps for video, speed for 4k, speed need for 4k, watch 4k, movies, watch football, youtube bandwidth, netflix, full hd, tv streaming speed | say_for: judge | say: Each video stream needs about 3–5 Mbps for HD, 5–8 Mbps for Full HD and 15–25 Mbps for 4K. -->
Common guidance per video stream: HD (720p) about 3–5 Mbps, Full HD (1080p) about 5–8 Mbps, 4K about 15–25 Mbps. Several TVs at once add up. Besides speed, the TV's Wi-Fi signal must be steady; a TV far from the router does better on 5 GHz with a fair signal, or wired. Apps lower the quality when the network is slow rather than stopping.

## Video calls and online classes
<!-- id: an.en.call | facts: an.call | src: general: common video-call recommendations | aliases: video call bandwidth, zoom, google meet, online class, online meeting, choppy video call, network for meetings, cable or wifi for a meeting | say_for: judge | say: A video call needs about 1–4 Mbps each way, but stability matters more: ping under about 100 ms and no signal drops. -->
A video call needs about 1–4 Mbps each way, but stability matters more: ping under about 100 ms, low jitter, no signal drops. Group calls with screen sharing need more upload. During a meeting or class, prioritise that device and avoid large downloads on other devices at the same time. If the device has a network port and a cable reaches the router, a cable is usually steadier than Wi-Fi; otherwise sit close to the router on the 5 GHz or 6 GHz band.

## Online exams
<!-- id: an.en.exam | facts: an.exam | src: general: online exam preparation; Router_App/router_display_src/LLM_JSON_CMD.md §5.12 | aliases: online exam, online test, prepare network for an exam, stable network for an exam, block schedule during the exam | say_for: howto | say: Before the exam, put the device near the router or wire it, check the network quality about 30 minutes before and prioritise that device. -->
Before an online exam: put the exam device near the router or wire it, check the network quality about 30 minutes before, prioritise that device for the exam window, look at the schedule list to make sure no block schedule overlaps the exam, and hold off large updates or game downloads on other devices.

## Online gaming
<!-- id: an.en.game | facts: an.game | src: general: online gaming network needs | aliases: gaming bandwidth, game lag, gaming ping, is the network good for gaming, what ping is good, game stutter | say_for: judge | say: Online games use little bandwidth but need low delay: a ping under about 50 ms is good, 50–100 ms playable, and over 100 ms noticeably laggy. -->
Online games use little bandwidth (usually under 5 Mbps) but need low, steady delay: a ping under about 50 ms is good, 50–100 ms playable, over 100 ms noticeably laggy; high jitter causes stutter. Game downloads and updates are the opposite and need a lot of bandwidth. A console is best on 5 GHz near the router or wired, and away from times when the home is downloading big files.

## Live streaming and upload
<!-- id: an.en.live | facts: an.live | src: general: common live-streaming recommendations | aliases: live stream bandwidth, going live, selling online live, upload speed, facebook live, tiktok live | say_for: judge | say: Live streaming depends on upload: about 3–5 Mbps for 720p, 6–10 Mbps for 1080p and 20 Mbps or more for 4K. -->
Live streaming depends on upload, not download. Common guidance: 720p about 3–5 Mbps, 1080p about 6–10 Mbps, 4K 20 Mbps or more, steady for the whole session, with 30–50 % to spare. Look at the upload part of the speed test, use a device near the router or wired, and temporarily limit other devices that upload a lot (for example a camera pushing to the cloud).

## Big downloads and updates
<!-- id: an.en.download | facts: an.download | src: general: bulk download behaviour | aliases: game download, windows update, large file download, hogging the network, one device slows everyone, download at night | say_for: howto | say: Limit the downloading device for a while, for example "Limit the console's download to 20 Mbps for 60 minutes", or leave big downloads for the night. -->
Game downloads, phone or computer updates and cloud backups can take almost the whole line and make other devices slow or choppy. Limit the downloading device for a while ("Limit the console's download to 20 Mbps for 60 minutes"), or leave big downloads for the night.

## How much a whole household needs
<!-- id: an.en.household | facts: an.household | src: general: household bandwidth estimate | aliases: what plan do i need, which speed plan, many people online, whole family online, bandwidth estimate | say_for: judge | say: Add up the activities that happen at the same time and keep 30–50 % to spare; an evening of about 50 Mbps is comfortable on a plan of 100 Mbps or more. -->
Add up the activities that can happen at the same time and keep 30–50 % to spare. An evening example: one TV in 4K (25 Mbps), two people on video calls (8 Mbps), a console (5 Mbps), a few phones browsing (10 Mbps) ≈ 50 Mbps, so a plan of 100 Mbps or more is comfortable. If the line is enough and things still stutter, the cause is usually the Wi-Fi signal to the device, not the plan.

## Comparing needs with a measurement
<!-- id: an.en.compare | facts: an.compare | src: llm/core/README.md (Network check); docs/speedtest.md | aliases: is my network enough, enough to watch, enough to stream, is my internet good enough, check before watching | say_for: howto,judge | say: Say "Check the network quality" so the router measures download, upload, ping and jitter, then compare with what that activity needs. -->
To know whether the network is enough for something, say "Check the network quality" so the router measures download, upload, ping and jitter, and compare with that activity's needs. The result is for the Internet line to the router; a device far away also depends on its own Wi-Fi signal. Measuring at the usual time of use (for example the evening) gives a more realistic picture.
