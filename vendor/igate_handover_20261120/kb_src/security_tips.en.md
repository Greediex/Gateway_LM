<!-- doc: security_tips.en | topic: security_tips | lang: en | as_of: 2026-11-08 | review: draft -->
# Keeping the home network safe

## What makes a strong Wi-Fi password
<!-- id: st.en.password | facts: st.password | src: general: password guidance | aliases: strong wifi password, weak password, set wifi password, safe password, 12345678, how long should the password be, change wifi password | say_for: judge,howto | say: A Wi-Fi password should be at least 12 characters with letters and digits; avoid digit runs, birthdays and phone numbers. -->
A Wi-Fi password should be at least 12 characters with both letters and digits, ideally a phrase easy for you to remember and hard for others to guess. Avoid digit runs (12345678), birthdays, phone numbers, the house or network name. A digits-only password is easy to crack. Change it when you suspect a stranger is on the network; afterwards every device has to enter it again.

## Wi-Fi security modes: WPA3, WPA2, open
<!-- id: st.en.encryption | facts: st.encryption | src: general: Wi-Fi security modes; docs/json_command_protocol.md §5.3 (encryption values) | aliases: wpa3, wpa2, wifi encryption, wifi security, network without password, open network, sae, psk, mixed | say_for: compare,judge | say: WPA3 is the safest mode today; WPA2 is still acceptable with a strong password, and an open network lets anyone nearby join. -->
WPA3 (SAE) is the safest mode today and is required on 6 GHz. WPA2 is still acceptable with a strong password. Mixed WPA2/WPA3 mode lets older devices connect. An open network (no password) lets anyone nearby join and see unencrypted traffic; use it only on purpose, for example a time-limited guest network.

## Use the guest network for guests and smart devices
<!-- id: st.en.guest | facts: st.guest | src: esp32/main/ui/ui_showcase_slides.c (Wi-Fi page); docs/voice_command_execution.md §4 | aliases: should i use the guest network, is the guest network safe, isolation, can guests see my devices, guest wifi for cameras | say_for: howto,judge | say: Put visitors on the guest network instead of the main one: you do not share the main password, it can turn itself off on a timer and you share it by QR code. -->
Put visitors on the guest network instead of the main one: you do not share the main password, it can turn itself off on a timer and you share it by QR code. The guest network is designed so guests cannot see the devices in your home; the actual isolation depends on the router's configuration, so ask whoever manages the network if you need to be sure. Turn the guest network off when it is not needed.

## The router's admin password
<!-- id: st.en.admin | facts: st.admin | src: docs/json_command_protocol.md §5.5 (set_password); general: router admin password | aliases: admin password, router login password, root, admin page, does the router need a password | say_for: define,judge | say: The router has its own admin password, separate from the Wi-Fi password; set a strong one of 8 to 128 characters. -->
The router has its own admin password, separate from the Wi-Fi password, for its configuration pages. Left empty or at a default, anyone on the home network can change the router's settings. Set a strong admin password (8 to 128 characters) and do not reuse the Wi-Fi password.

## What double NAT is
<!-- id: st.en.nat | facts: st.nat | src: general: double NAT; Router_App/router_context_src/kb/src/metric_glossary.en.md (mg.en.wan) | aliases: double nat, router behind a modem, two routers, port forwarding does not work, cannot view camera remotely, bridge mode, private wan address | say_for: define | say: Double NAT happens when the router sits behind another modem or router that also shares addresses; the Internet works, but port forwarding, some games and calls may have trouble. -->
Double NAT happens when the router sits behind another modem or router that also shares addresses: the router's WAN address is a private one (starting with 192.168., 10. or 172.16–31.). The Internet works normally, but port forwarding, remote camera viewing, some games and calls may have trouble. The usual fix is to put the provider's modem in bridge mode so this router gets an address directly.

## UPnP and port forwarding
<!-- id: st.en.upnp | facts: st.upnp | src: general: UPnP and port forwarding | aliases: upnp, open a port, port forwarding, ports open to the internet, game needs open ports, strict nat | say_for: define,judge | say: Port forwarding lets connections from the Internet reach a device at home, and UPnP lets devices open ports by themselves; turn them on only when really needed. -->
Port forwarding lets connections from the Internet reach a device at home, for example a camera or a game server. UPnP lets devices open ports by themselves without asking. Convenient but risky: an infected device can open ports too. Turn UPnP on or forward a port only when you really need it, and close it when you no longer do.

## Should WPS be on or off
<!-- id: st.en.wps | facts: st.wps | src: general: WPS weaknesses | aliases: wps, wps button, push button connect, wps pin, should i enable wps | say_for: judge,define | say: WPS lets a device connect with a button or a PIN instead of typing the password; it is best kept off, because the PIN method has well-known weaknesses. -->
WPS lets a device connect with a button or a PIN instead of typing the password. The PIN method has well-known weaknesses, so it is best to keep WPS off and connect with the password or a QR code.

## Cameras and smart devices
<!-- id: st.en.iot | facts: st.iot | src: general: IoT security; esp32/main/ui/ui_showcase_slides.c (AI Security page) | aliases: is my camera safe, camera hacked, smart devices, iot, default camera password, update the camera | say_for: howto | say: Change the default password of cameras and smart devices, keep their firmware updated and turn off remote viewing if you do not use it. -->
Cameras and smart devices are frequent targets because they keep default passwords and are rarely updated. Change the device's default password, keep its app and firmware updated, and turn off remote viewing if you do not use it. The router's AI Security watches for signs such as an infected camera or a port scan and shows them on the screen.

## What to do about an unknown device
<!-- id: st.en.unknown | facts: st.unknown | src: docs/device_labels.md §6; esp32/main/ui/ui_showcase_slides.c (AI Security page) | aliases: unknown device, strange device, who is on my wifi, stranger on my wifi, block unknown device, someone stealing wifi | say_for: howto | say: First check whether it is a family device that changed its private MAC; if you do not know it, block it and then change the Wi-Fi password. -->
First check whether it is a family device that changed its private MAC address (its name, type, when it joined). If it is yours, label it so you recognise it next time. If you do not know it, block it ("Block <device name>") and then change the Wi-Fi password so the stranger cannot come back, because a device that changes its MAC can rejoin after a block.

## What AI Security alerts mean
<!-- id: st.en.alerts | facts: st.alerts | src: docs/ai_security_events.md §1-2 | aliases: what does this security alert mean, what is a port scan, ddos, under attack, infected device, high severity event, is it dangerous | say_for: define | say: Each AI Security alert is a sign to check, for example a port scan is one device probing which ports others have open; an alert is not proof that the device was hacked. -->
AI Security names each event: a port scan (one device probing which ports others have open), a denial-of-service (DDoS) attack, an intrusion, a device suspected of malware, a new device joining. High severity means act now: see which device caused it, block it if you do not recognise it, change the Wi-Fi password. An alert is a sign to check, not proof that the device was hacked.

## Updating the router's software
<!-- id: st.en.update | facts: st.update | src: general: firmware updates | aliases: update the router, router software, firmware, new version, is there an update, upgrade the router | say_for: howto,judge | say: Updating the router's software fixes security holes; if your provider sends you an update, follow their instructions. -->
Updating the router's software fixes security holes and bugs. The router does not know about new versions when it has no update source; if your provider sends you an update, follow their instructions. iGate does not download or install updates by itself.
