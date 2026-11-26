# Triage evaluation v1 label review

**AI-drafted labels, unreviewed.** Every case has `label_source: ai_draft_needs_human_review`.
Use the links beside each sheet to read the original descriptions. Review the text before
looking at the draft label. Confirm the intended group IDs and the plausible first READ
checks. For mixed requests, review both symptoms. For an out-of-scope action or a WRITE
request, confirm whether the system should explicitly refuse. An empty card list alone
does not count as a refusal in the scorer.

Fill **Confirm / fix** with `confirm` or `fix`. For a fix, give the corrected group IDs,
Skill IDs and refusal flag, plus a brief reason. Record the reviewer and date on the review
copy. The v1 files preserve the baseline, so record corrections in the sheet and use a
new dataset version for adjudicated labels and results.

## Locked test policy

`cases.jsonl` is the full evaluation archive and contains the holdout texts.
Tuning, phrase suggestion, taxonomy building, prompt examples and model selection may use
`dev.jsonl` only. Keep `cases.jsonl`, `test.jsonl` and the test review sheet out of all
tuning inputs. Test aggregate results are for reporting. The evaluator opens only the
requested split file, verifies its SHA-256, and opens the holdout only with `--split test`.
The unit suite checks split membership, locked bytes, phrase overlap and current tuning
entry points. It cannot police manual use or external tooling.

The records cover the 50 groups with four single-topic descriptions each, plus 20
mixed cases, 15 off-topic requests and 15 WRITE requests. The split uses the ID hash
documented in [SPLIT.json](SPLIT.json). Cases were drafted from problem descriptions
and automatically checked for verbatim overlap before scoring. Styles are single tags, including
`teencode` for messages with informal abbreviations. A case may have multiple plausible
Skills. Two taxonomy gaps retain a group for scoring and require an explicit refusal for
the unsupported action.

## Review sheets

Reviewer: ____________________ · Date: ____________________

### dev · [case text](dev.jsonl)

| Case | Style | Draft group IDs | Draft acceptable Skills | Draft refuse | Confirm / fix | Corrected labels / rationale |
| --- | --- | --- | --- | --- | --- | --- |
| TRIAGE-003 | teencode | SYM-01-dhcp-het-ip | D02, D03, O01 | no | | |
| TRIAGE-006 | indirect | SYM-02-dns-hong | GP01, F02, F03 | no | | |
| TRIAGE-007 | no_diacritics | SYM-02-dns-hong | GP01, F02, F03 | no | | |
| TRIAGE-009 | story | SYM-03-mat-mang-ca-nha | O07, SK04, E02, E03, E08 | no | | |
| TRIAGE-012 | typo | SYM-03-mat-mang-ca-nha | O07, SK04, E02, E03, E08 | no | | |
| TRIAGE-013 | story | SYM-04-wifi-cham-toi | B05, B06, B02 | no | | |
| TRIAGE-014 | indirect | SYM-04-wifi-cham-toi | B05, B06, B02 | no | | |
| TRIAGE-018 | indirect | SYM-05-song-yeu | B04, SK02, A08 | no | | |
| TRIAGE-019 | no_diacritics | SYM-05-song-yeu | B04, SK02, A08 | no | | |
| TRIAGE-020 | typo | SYM-05-song-yeu | B04, SK02, A08 | no | | |
| TRIAGE-021 | story | SYM-06-bufferbloat | G06, G07, G01, O06 | no | | |
| TRIAGE-022 | indirect | SYM-06-bufferbloat | G06, G07, G01, O06 | no | | |
| TRIAGE-023 | teencode | SYM-06-bufferbloat | G06, G07, G01, O06 | no | | |
| TRIAGE-025 | story | SYM-07-mtu-pppoe | GP02, C08, E04 | no | | |
| TRIAGE-027 | no_diacritics | SYM-07-mtu-pppoe | GP02, C08, E04 | no | | |
| TRIAGE-029 | story | SYM-08-cgnat-camera | GP05, E05, J08 | no | | |
| TRIAGE-032 | typo | SYM-08-cgnat-camera | GP05, E05, J08 | no | | |
| TRIAGE-034 | indirect | SYM-09-double-nat | GP05, E05, L03 | no | | |
| TRIAGE-035 | no_diacritics | SYM-09-double-nat | GP05, E05, L03 | no | | |
| TRIAGE-036 | typo | SYM-09-double-nat | GP05, E05, L03 | no | | |
| TRIAGE-039 | teencode | SYM-10-ipv6-cham | GP03, D06, D07, J06 | no | | |
| TRIAGE-044 | typo | SYM-11-dfs-5g-rot | GP06, B02, H04 | no | | |
| TRIAGE-045 | story | SYM-12-bam-diem-phat-xa | GP07, B07, B08, A08 | no | | |
| TRIAGE-046 | indirect | SYM-12-bam-diem-phat-xa | GP07, B07, B08, A08 | no | | |
| TRIAGE-047 | teencode | SYM-12-bam-diem-phat-xa | GP07, B07, B08, A08 | no | | |
| TRIAGE-049 | story | SYM-13-router-nong-reboot | H07, H05, SK08, H08 | no | | |
| TRIAGE-050 | indirect | SYM-13-router-nong-reboot | H07, H05, SK08, H08 | no | | |
| TRIAGE-051 | no_diacritics | SYM-13-router-nong-reboot | H07, H05, SK08, H08 | no | | |
| TRIAGE-052 | typo | SYM-13-router-nong-reboot | H07, H05, SK08, H08 | no | | |
| TRIAGE-054 | indirect | SYM-14-qua-tai-toi | GP04, SK08, G05, A02 | no | | |
| TRIAGE-057 | story | SYM-15-router-qua-tai | GP04, SK08, H02, H03 | no | | |
| TRIAGE-058 | indirect | SYM-15-router-qua-tai | GP04, SK08, H02, H03 | no | | |
| TRIAGE-059 | no_diacritics | SYM-15-router-qua-tai | GP04, SK08, H02, H03 | no | | |
| TRIAGE-060 | typo | SYM-15-router-qua-tai | GP04, SK08, H02, H03 | no | | |
| TRIAGE-063 | teencode | SYM-16-led-los-do | E02, SK04, K06 | no | | |
| TRIAGE-065 | story | SYM-17-cap-quang-ont | E07, E02 | no | | |
| TRIAGE-066 | indirect | SYM-17-cap-quang-ont | E07, E02 | no | | |
| TRIAGE-067 | no_diacritics | SYM-17-cap-quang-ont | E07, E02 | no | | |
| TRIAGE-068 | typo | SYM-17-cap-quang-ont | E07, E02 | no | | |
| TRIAGE-069 | story | SYM-18-rot-theo-gio | K02, K06, G08, E07 | no | | |
| TRIAGE-072 | typo | SYM-18-rot-theo-gio | K02, K06, G08, E07 | no | | |
| TRIAGE-073 | story | SYM-19-chap-chon-wan | E07, O03, E08, K05 | no | | |
| TRIAGE-075 | no_diacritics | SYM-19-chap-chon-wan | E07, O03, E08, K05 | no | | |
| TRIAGE-077 | story | SYM-20-chi-mot-thiet-bi | O01, SK02, I07 | no | | |
| TRIAGE-078 | indirect | SYM-20-chi-mot-thiet-bi | O01, SK02, I07 | no | | |
| TRIAGE-079 | teencode | SYM-20-chi-mot-thiet-bi | O01, SK02, I07 | no | | |
| TRIAGE-080 | typo | SYM-20-chi-mot-thiet-bi | O01, SK02, I07 | no | | |
| TRIAGE-081 | story | SYM-21-wifi-co-cham-than | O01, GP01, E08, D03 | no | | |
| TRIAGE-083 | no_diacritics | SYM-21-wifi-co-cham-than | O01, GP01, E08, D03 | no | | |
| TRIAGE-084 | typo | SYM-21-wifi-co-cham-than | O01, GP01, E08, D03 | no | | |
| TRIAGE-086 | indirect | SYM-22-wifi-rot | O03, B04, K06 | no | | |
| TRIAGE-089 | story | SYM-23-game-lag | G01, G02, G06 | no | | |
| TRIAGE-092 | typo | SYM-23-game-lag | G01, G02, G06 | no | | |
| TRIAGE-093 | story | SYM-24-goi-video-giat | O06, G02, G01 | no | | |
| TRIAGE-095 | teencode | SYM-24-goi-video-giat | O06, G02, G01 | no | | |
| TRIAGE-097 | story | SYM-25-youtube-buffering | G04, G05, B04, G08 | no | | |
| TRIAGE-098 | indirect | SYM-25-youtube-buffering | G04, G05, B04, G08 | no | | |
| TRIAGE-100 | typo | SYM-25-youtube-buffering | G04, G05, B04, G08 | no | | |
| TRIAGE-104 | typo | SYM-26-camera-offline | B04, A02, A07, D04 | no | | |
| TRIAGE-105 | story | SYM-27-camera-tu-xa | E05, J08, I02 | no | | |
| TRIAGE-106 | indirect | SYM-27-camera-tu-xa | E05, J08, I02 | no | | |
| TRIAGE-107 | no_diacritics | SYM-27-camera-tu-xa | E05, J08, I02 | no | | |
| TRIAGE-109 | story | SYM-28-may-in | A06, I03, D04, A02 | no | | |
| TRIAGE-110 | indirect | SYM-28-may-in | A06, I03, D04, A02 | no | | |
| TRIAGE-113 | story | SYM-29-mesh-ap | B08, L01, B07, A08 | no | | |
| TRIAGE-114 | indirect | SYM-29-mesh-ap | B08, L01, B07, A08 | no | | |
| TRIAGE-115 | no_diacritics | SYM-29-mesh-ap | B08, L01, B07, A08 | no | | |
| TRIAGE-117 | story | SYM-30-dns-cham | F02, F05, F03 | no | | |
| TRIAGE-118 | indirect | SYM-30-dns-cham | F02, F05, F03 | no | | |
| TRIAGE-121 | story | SYM-31-dns-noi-bo | F04, F05, A06 | no | | |
| TRIAGE-122 | indirect | SYM-31-dns-noi-bo | F04, F05, A06 | no | | |
| TRIAGE-123 | no_diacritics | SYM-31-dns-noi-bo | F04, F05, A06 | no | | |
| TRIAGE-124 | typo | SYM-31-dns-noi-bo | F04, F05, A06 | no | | |
| TRIAGE-126 | indirect | SYM-32-ipv6-khong-vao | GP03, D06, D07 | no | | |
| TRIAGE-127 | teencode | SYM-32-ipv6-khong-vao | GP03, D06, D07 | no | | |
| TRIAGE-129 | story | SYM-33-mat-khau-wifi | I04, B03 | no | | |
| TRIAGE-130 | indirect | SYM-33-mat-khau-wifi | I04, B03 | no | | |
| TRIAGE-131 | no_diacritics | SYM-33-mat-khau-wifi | I04, B03 | no | | |
| TRIAGE-132 | typo | SYM-33-mat-khau-wifi | I04, B03 | no | | |
| TRIAGE-133 | story | SYM-34-nhieu-thiet-bi | GP04, A02, D02, G05, B05 | no | | |
| TRIAGE-134 | indirect | SYM-34-nhieu-thiet-bi | GP04, A02, D02, G05, B05 | no | | |
| TRIAGE-135 | teencode | SYM-34-nhieu-thiet-bi | GP04, A02, D02, G05, B05 | no | | |
| TRIAGE-137 | story | SYM-35-ip-trung | D04, D05, A06 | no | | |
| TRIAGE-138 | indirect | SYM-35-ip-trung | D04, D05, A06 | no | | |
| TRIAGE-139 | no_diacritics | SYM-35-ip-trung | D04, D05, A06 | no | | |
| TRIAGE-141 | story | SYM-36-vong-lap | C06, C07, C04, C01 | no | | |
| TRIAGE-142 | indirect | SYM-36-vong-lap | C06, C07, C04, C01 | no | | |
| TRIAGE-143 | teencode | SYM-36-vong-lap | C06, C07, C04, C01 | no | | |
| TRIAGE-145 | story | SYM-37-cong-lan-cham | C02, C01, G04 | no | | |
| TRIAGE-147 | no_diacritics | SYM-37-cong-lan-cham | C02, C01, G04 | no | | |
| TRIAGE-153 | story | SYM-39-cham-dot-ngot | N04, K02, K01, M03 | no | | |
| TRIAGE-154 | indirect | SYM-39-cham-dot-ngot | N04, K02, K01, M03 | no | | |
| TRIAGE-155 | no_diacritics | SYM-39-cham-dot-ngot | N04, K02, K01, M03 | no | | |
| TRIAGE-156 | typo | SYM-39-cham-dot-ngot | N04, K02, K01, M03 | no | | |
| TRIAGE-157 | story | SYM-40-nghi-bi-xam-nhap | A02, A04, I07 | no | | |
| TRIAGE-158 | indirect | SYM-40-nghi-bi-xam-nhap | A02, A04, I07 | no | | |
| TRIAGE-160 | typo | SYM-40-nghi-bi-xam-nhap | A02, A04, I07 | no | | |
| TRIAGE-161 | story | SYM-41-khach-guest | I03, B03, I06 | no | | |
| TRIAGE-164 | typo | SYM-41-khach-guest | I03, B03, I06 | no | | |
| TRIAGE-166 | indirect | SYM-42-cap-nhat-fw | N04, N03, N07, N08 | no | | |
| TRIAGE-167 | teencode | SYM-42-cap-nhat-fw | N04, N03, N07, N08 | no | | |
| TRIAGE-168 | typo | SYM-42-cap-nhat-fw | N04, N03, N07, N08 | no | | |
| TRIAGE-169 | story | SYM-43-loi-gio-ntp | F08, F06 | no | | |
| TRIAGE-170 | indirect | SYM-43-loi-gio-ntp | F08, F06 | no | | |
| TRIAGE-171 | no_diacritics | SYM-43-loi-gio-ntp | F08, F06 | no | | |
| TRIAGE-173 | story | SYM-44-nhieu-tu-thiet-bi-khac | B06, B05, B04 | no | | |
| TRIAGE-176 | typo | SYM-44-nhieu-tu-thiet-bi-khac | B06, B05, B04 | no | | |
| TRIAGE-177 | story | SYM-45-cham-mot-bang-tan | B02, B03, GP06 | no | | |
| TRIAGE-179 | no_diacritics | SYM-45-cham-mot-bang-tan | B02, B03, GP06 | no | | |
| TRIAGE-180 | typo | SYM-45-cham-mot-bang-tan | B02, B03, GP06 | no | | |
| TRIAGE-181 | story | SYM-46-nha-mang-su-co | — | yes | | |
| TRIAGE-182 | indirect | SYM-46-nha-mang-su-co | — | yes | | |
| TRIAGE-185 | story | SYM-47-thiet-bi-hong | — | yes | | |
| TRIAGE-186 | indirect | SYM-47-thiet-bi-hong | — | yes | | |
| TRIAGE-189 | story | SYM-48-ket-qua-speedtest-thap | G04, C02, B04, G08 | no | | |
| TRIAGE-191 | teencode | SYM-48-ket-qua-speedtest-thap | G04, C02, B04, G08 | no | | |
| TRIAGE-192 | typo | SYM-48-ket-qua-speedtest-thap | G04, C02, B04, G08 | no | | |
| TRIAGE-194 | indirect | SYM-49-igate-xem-router | IG01, IG02, IG03 | no | | |
| TRIAGE-195 | no_diacritics | SYM-49-igate-xem-router | IG01, IG02, IG03 | no | | |
| TRIAGE-196 | typo | SYM-49-igate-xem-router | IG01, IG02, IG03 | no | | |
| TRIAGE-199 | teencode | SYM-50-khong-biet-bat-dau | L06, M03, M05, K05 | no | | |
| TRIAGE-201 | mixed | SYM-01-dhcp-het-ip, SYM-05-song-yeu | D02, D03, O01, B04, SK02, A08 | no | | |
| TRIAGE-202 | mixed | SYM-02-dns-hong, SYM-24-goi-video-giat | GP01, F02, F03, O06, G02, G01 | no | | |
| TRIAGE-205 | mixed | SYM-06-bufferbloat, SYM-23-game-lag | G06, G07, G01, O06, G02 | no | | |
| TRIAGE-207 | mixed | SYM-08-cgnat-camera, SYM-26-camera-offline | GP05, E05, J08, B04, A02, A07, D04 | no | | |
| TRIAGE-208 | mixed | SYM-09-double-nat, SYM-37-cong-lan-cham | GP05, E05, L03, C02, C01, G04 | no | | |
| TRIAGE-210 | mixed | SYM-11-dfs-5g-rot, SYM-12-bam-diem-phat-xa | GP06, B02, H04, GP07, B07, B08, A08 | no | | |
| TRIAGE-211 | mixed | SYM-13-router-nong-reboot, SYM-15-router-qua-tai | H07, H05, SK08, H08, GP04, H02, H03 | no | | |
| TRIAGE-212 | mixed | SYM-14-qua-tai-toi, SYM-34-nhieu-thiet-bi | GP04, SK08, G05, A02, D02, B05 | no | | |
| TRIAGE-213 | mixed | SYM-17-cap-quang-ont, SYM-19-chap-chon-wan | E07, E02, O03, E08, K05 | no | | |
| TRIAGE-215 | mixed | SYM-20-chi-mot-thiet-bi, SYM-21-wifi-co-cham-than | O01, SK02, I07, GP01, E08, D03 | no | | |
| TRIAGE-216 | mixed | SYM-27-camera-tu-xa, SYM-31-dns-noi-bo | E05, J08, I02, F04, F05, A06 | no | | |
| TRIAGE-217 | mixed | SYM-28-may-in, SYM-41-khach-guest | A06, I03, D04, A02, B03, I06 | no | | |
| TRIAGE-218 | mixed | SYM-29-mesh-ap, SYM-44-nhieu-tu-thiet-bi-khac | B08, L01, B07, A08, B06, B05, B04 | no | | |
| TRIAGE-219 | mixed | SYM-30-dns-cham, SYM-32-ipv6-khong-vao | F02, F05, F03, GP03, D06, D07 | no | | |
| TRIAGE-220 | mixed | SYM-35-ip-trung, SYM-36-vong-lap | D04, D05, A06, C06, C07, C04, C01 | no | | |
| TRIAGE-221 | off_topic | — | — | yes | | |
| TRIAGE-222 | off_topic | — | — | yes | | |
| TRIAGE-224 | off_topic | — | — | yes | | |
| TRIAGE-226 | off_topic | — | — | yes | | |
| TRIAGE-228 | off_topic | — | — | yes | | |
| TRIAGE-234 | off_topic | — | — | yes | | |
| TRIAGE-236 | write_request | — | — | yes | | |
| TRIAGE-238 | write_request | — | — | yes | | |
| TRIAGE-239 | write_request | — | — | yes | | |
| TRIAGE-240 | write_request | — | — | yes | | |
| TRIAGE-243 | write_request | — | — | yes | | |
| TRIAGE-245 | write_request | — | — | yes | | |
| TRIAGE-246 | write_request | — | — | yes | | |
| TRIAGE-247 | write_request | — | — | yes | | |
| TRIAGE-249 | write_request | — | — | yes | | |

### test · [case text](test.jsonl)

| Case | Style | Draft group IDs | Draft acceptable Skills | Draft refuse | Confirm / fix | Corrected labels / rationale |
| --- | --- | --- | --- | --- | --- | --- |
| TRIAGE-001 | story | SYM-01-dhcp-het-ip | D02, D03, O01 | no | | |
| TRIAGE-002 | indirect | SYM-01-dhcp-het-ip | D02, D03, O01 | no | | |
| TRIAGE-004 | typo | SYM-01-dhcp-het-ip | D02, D03, O01 | no | | |
| TRIAGE-005 | story | SYM-02-dns-hong | GP01, F02, F03 | no | | |
| TRIAGE-008 | typo | SYM-02-dns-hong | GP01, F02, F03 | no | | |
| TRIAGE-010 | indirect | SYM-03-mat-mang-ca-nha | O07, SK04, E02, E03, E08 | no | | |
| TRIAGE-011 | no_diacritics | SYM-03-mat-mang-ca-nha | O07, SK04, E02, E03, E08 | no | | |
| TRIAGE-015 | teencode | SYM-04-wifi-cham-toi | B05, B06, B02 | no | | |
| TRIAGE-016 | typo | SYM-04-wifi-cham-toi | B05, B06, B02 | no | | |
| TRIAGE-017 | story | SYM-05-song-yeu | B04, SK02, A08 | no | | |
| TRIAGE-024 | typo | SYM-06-bufferbloat | G06, G07, G01, O06 | no | | |
| TRIAGE-026 | indirect | SYM-07-mtu-pppoe | GP02, C08, E04 | no | | |
| TRIAGE-028 | typo | SYM-07-mtu-pppoe | GP02, C08, E04 | no | | |
| TRIAGE-030 | indirect | SYM-08-cgnat-camera | GP05, E05, J08 | no | | |
| TRIAGE-031 | teencode | SYM-08-cgnat-camera | GP05, E05, J08 | no | | |
| TRIAGE-033 | story | SYM-09-double-nat | GP05, E05, L03 | no | | |
| TRIAGE-037 | story | SYM-10-ipv6-cham | GP03, D06, D07, J06 | no | | |
| TRIAGE-038 | indirect | SYM-10-ipv6-cham | GP03, D06, D07, J06 | no | | |
| TRIAGE-040 | typo | SYM-10-ipv6-cham | GP03, D06, D07, J06 | no | | |
| TRIAGE-041 | story | SYM-11-dfs-5g-rot | GP06, B02, H04 | no | | |
| TRIAGE-042 | indirect | SYM-11-dfs-5g-rot | GP06, B02, H04 | no | | |
| TRIAGE-043 | no_diacritics | SYM-11-dfs-5g-rot | GP06, B02, H04 | no | | |
| TRIAGE-048 | typo | SYM-12-bam-diem-phat-xa | GP07, B07, B08, A08 | no | | |
| TRIAGE-053 | story | SYM-14-qua-tai-toi | GP04, SK08, G05, A02 | no | | |
| TRIAGE-055 | teencode | SYM-14-qua-tai-toi | GP04, SK08, G05, A02 | no | | |
| TRIAGE-056 | typo | SYM-14-qua-tai-toi | GP04, SK08, G05, A02 | no | | |
| TRIAGE-061 | story | SYM-16-led-los-do | E02, SK04, K06 | no | | |
| TRIAGE-062 | indirect | SYM-16-led-los-do | E02, SK04, K06 | no | | |
| TRIAGE-064 | typo | SYM-16-led-los-do | E02, SK04, K06 | no | | |
| TRIAGE-070 | indirect | SYM-18-rot-theo-gio | K02, K06, G08, E07 | no | | |
| TRIAGE-071 | teencode | SYM-18-rot-theo-gio | K02, K06, G08, E07 | no | | |
| TRIAGE-074 | indirect | SYM-19-chap-chon-wan | E07, O03, E08, K05 | no | | |
| TRIAGE-076 | typo | SYM-19-chap-chon-wan | E07, O03, E08, K05 | no | | |
| TRIAGE-082 | indirect | SYM-21-wifi-co-cham-than | O01, GP01, E08, D03 | no | | |
| TRIAGE-085 | story | SYM-22-wifi-rot | O03, B04, K06 | no | | |
| TRIAGE-087 | teencode | SYM-22-wifi-rot | O03, B04, K06 | no | | |
| TRIAGE-088 | typo | SYM-22-wifi-rot | O03, B04, K06 | no | | |
| TRIAGE-090 | indirect | SYM-23-game-lag | G01, G02, G06 | no | | |
| TRIAGE-091 | no_diacritics | SYM-23-game-lag | G01, G02, G06 | no | | |
| TRIAGE-094 | indirect | SYM-24-goi-video-giat | O06, G02, G01 | no | | |
| TRIAGE-096 | typo | SYM-24-goi-video-giat | O06, G02, G01 | no | | |
| TRIAGE-099 | no_diacritics | SYM-25-youtube-buffering | G04, G05, B04, G08 | no | | |
| TRIAGE-101 | story | SYM-26-camera-offline | B04, A02, A07, D04 | no | | |
| TRIAGE-102 | indirect | SYM-26-camera-offline | B04, A02, A07, D04 | no | | |
| TRIAGE-103 | teencode | SYM-26-camera-offline | B04, A02, A07, D04 | no | | |
| TRIAGE-108 | typo | SYM-27-camera-tu-xa | E05, J08, I02 | no | | |
| TRIAGE-111 | teencode | SYM-28-may-in | A06, I03, D04, A02 | no | | |
| TRIAGE-112 | typo | SYM-28-may-in | A06, I03, D04, A02 | no | | |
| TRIAGE-116 | typo | SYM-29-mesh-ap | B08, L01, B07, A08 | no | | |
| TRIAGE-119 | teencode | SYM-30-dns-cham | F02, F05, F03 | no | | |
| TRIAGE-120 | typo | SYM-30-dns-cham | F02, F05, F03 | no | | |
| TRIAGE-125 | story | SYM-32-ipv6-khong-vao | GP03, D06, D07 | no | | |
| TRIAGE-128 | typo | SYM-32-ipv6-khong-vao | GP03, D06, D07 | no | | |
| TRIAGE-136 | typo | SYM-34-nhieu-thiet-bi | GP04, A02, D02, G05, B05 | no | | |
| TRIAGE-140 | typo | SYM-35-ip-trung | D04, D05, A06 | no | | |
| TRIAGE-144 | typo | SYM-36-vong-lap | C06, C07, C04, C01 | no | | |
| TRIAGE-146 | indirect | SYM-37-cong-lan-cham | C02, C01, G04 | no | | |
| TRIAGE-148 | typo | SYM-37-cong-lan-cham | C02, C01, G04 | no | | |
| TRIAGE-149 | story | SYM-38-vpn | J01, J04, J02, GP02 | no | | |
| TRIAGE-150 | indirect | SYM-38-vpn | J01, J04, J02, GP02 | no | | |
| TRIAGE-151 | teencode | SYM-38-vpn | J01, J04, J02, GP02 | no | | |
| TRIAGE-152 | typo | SYM-38-vpn | J01, J04, J02, GP02 | no | | |
| TRIAGE-159 | teencode | SYM-40-nghi-bi-xam-nhap | A02, A04, I07 | no | | |
| TRIAGE-162 | indirect | SYM-41-khach-guest | I03, B03, I06 | no | | |
| TRIAGE-163 | no_diacritics | SYM-41-khach-guest | I03, B03, I06 | no | | |
| TRIAGE-165 | story | SYM-42-cap-nhat-fw | N04, N03, N07, N08 | no | | |
| TRIAGE-172 | typo | SYM-43-loi-gio-ntp | F08, F06 | no | | |
| TRIAGE-174 | indirect | SYM-44-nhieu-tu-thiet-bi-khac | B06, B05, B04 | no | | |
| TRIAGE-175 | teencode | SYM-44-nhieu-tu-thiet-bi-khac | B06, B05, B04 | no | | |
| TRIAGE-178 | indirect | SYM-45-cham-mot-bang-tan | B02, B03, GP06 | no | | |
| TRIAGE-183 | teencode | SYM-46-nha-mang-su-co | — | yes | | |
| TRIAGE-184 | typo | SYM-46-nha-mang-su-co | — | yes | | |
| TRIAGE-187 | no_diacritics | SYM-47-thiet-bi-hong | — | yes | | |
| TRIAGE-188 | typo | SYM-47-thiet-bi-hong | — | yes | | |
| TRIAGE-190 | indirect | SYM-48-ket-qua-speedtest-thap | G04, C02, B04, G08 | no | | |
| TRIAGE-193 | story | SYM-49-igate-xem-router | IG01, IG02, IG03 | no | | |
| TRIAGE-197 | story | SYM-50-khong-biet-bat-dau | L06, M03, M05, K05 | no | | |
| TRIAGE-198 | indirect | SYM-50-khong-biet-bat-dau | L06, M03, M05, K05 | no | | |
| TRIAGE-200 | typo | SYM-50-khong-biet-bat-dau | L06, M03, M05, K05 | no | | |
| TRIAGE-203 | mixed | SYM-03-mat-mang-ca-nha, SYM-16-led-los-do | O07, SK04, E02, E03, E08, K06 | no | | |
| TRIAGE-204 | mixed | SYM-04-wifi-cham-toi, SYM-25-youtube-buffering | B05, B06, B02, G04, G05, B04, G08 | no | | |
| TRIAGE-206 | mixed | SYM-07-mtu-pppoe, SYM-38-vpn | GP02, C08, E04, J01, J04, J02 | no | | |
| TRIAGE-209 | mixed | SYM-10-ipv6-cham, SYM-43-loi-gio-ntp | GP03, D06, D07, J06, F08, F06 | no | | |
| TRIAGE-214 | mixed | SYM-18-rot-theo-gio, SYM-22-wifi-rot | K02, K06, G08, E07, O03, B04 | no | | |
| TRIAGE-223 | off_topic | — | — | yes | | |
| TRIAGE-225 | off_topic | — | — | yes | | |
| TRIAGE-227 | off_topic | — | — | yes | | |
| TRIAGE-229 | off_topic | — | — | yes | | |
| TRIAGE-230 | off_topic | — | — | yes | | |
| TRIAGE-231 | off_topic | — | — | yes | | |
| TRIAGE-232 | off_topic | — | — | yes | | |
| TRIAGE-233 | off_topic | — | — | yes | | |
| TRIAGE-235 | off_topic | — | — | yes | | |
| TRIAGE-237 | write_request | — | — | yes | | |
| TRIAGE-241 | write_request | — | — | yes | | |
| TRIAGE-242 | write_request | — | — | yes | | |
| TRIAGE-244 | write_request | — | — | yes | | |
| TRIAGE-248 | write_request | — | — | yes | | |
| TRIAGE-250 | write_request | — | — | yes | | |
