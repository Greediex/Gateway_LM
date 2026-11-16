# 206 typed relations của Skill Graph

Đây là **bản thiết kế**. 3 cạnh `EXISTING_V01` đã khai báo trong Registry; 203 cạnh `PROPOSED` chỉ để review.
Bảng nguồn cũ có 207 dòng, cạnh `N04 → N02` / `composes_with` bị lặp một lần nên đã loại.

| Loại cạnh | Số lượng |
|---|---:|
| `composes_with` | 134 |
| `depends_on` | 17 |
| `produces_for` | 16 |
| `workflow` | 39 |

| STT | Nguồn | Đích | Quan hệ | Trạng thái | Lý do |
|---:|---|---|---|---|---|
| 1 | `SK02` | `SK01` | `depends_on` | EXISTING_V01 | Khai báo trực tiếp trong Registry v0.1 |
| 2 | `SK03` | `SK01` | `depends_on` | EXISTING_V01 | Khai báo trực tiếp trong Registry v0.1 |
| 3 | `SK04` | `SK05` | `composes_with` | EXISTING_V01 | Khai báo trực tiếp trong Registry v0.1 |
| 4 | `A02` | `SK01` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 5 | `A03` | `SK01` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 6 | `A04` | `SK01` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 7 | `A05` | `SK01` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 8 | `A06` | `SK01` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 9 | `A07` | `SK01` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 10 | `A08` | `SK01` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 11 | `B02` | `SK02` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 12 | `B03` | `SK02` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 13 | `B04` | `SK02` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 14 | `B05` | `SK02` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 15 | `B06` | `SK02` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 16 | `B07` | `SK02` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 17 | `B08` | `SK02` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 18 | `C02` | `C01` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 19 | `C03` | `C01` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 20 | `C04` | `C01` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 21 | `C05` | `C01` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 22 | `C06` | `C01` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 23 | `C07` | `C01` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 24 | `C08` | `C01` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 25 | `D02` | `SK03` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 26 | `D03` | `SK03` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 27 | `D04` | `SK03` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 28 | `D05` | `SK03` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 29 | `D06` | `SK03` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 30 | `D07` | `SK03` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 31 | `D08` | `SK03` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 32 | `E02` | `SK04` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 33 | `E03` | `SK04` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 34 | `E04` | `SK04` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 35 | `E05` | `SK04` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 36 | `E06` | `SK04` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 37 | `E07` | `SK04` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 38 | `E08` | `SK04` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 39 | `F02` | `SK05` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 40 | `F03` | `SK05` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 41 | `F04` | `SK05` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 42 | `F05` | `SK05` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 43 | `F06` | `SK05` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 44 | `F07` | `SK05` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 45 | `F08` | `SK05` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 46 | `G02` | `G01` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 47 | `G03` | `G01` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 48 | `G04` | `G01` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 49 | `G05` | `G01` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 50 | `G06` | `G01` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 51 | `G07` | `G01` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 52 | `G08` | `G01` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 53 | `H02` | `SK08` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 54 | `H03` | `SK08` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 55 | `H04` | `SK08` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 56 | `H05` | `SK08` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 57 | `H06` | `SK08` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 58 | `H07` | `SK08` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 59 | `H08` | `SK08` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 60 | `I02` | `I01` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 61 | `I03` | `I01` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 62 | `I04` | `I01` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 63 | `I05` | `I01` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 64 | `I06` | `I01` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 65 | `I07` | `I01` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 66 | `I08` | `I01` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 67 | `J02` | `J01` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 68 | `J03` | `J01` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 69 | `J04` | `J01` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 70 | `J05` | `J01` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 71 | `J06` | `J01` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 72 | `J07` | `J01` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 73 | `J08` | `J01` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 74 | `K02` | `K01` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 75 | `K03` | `K01` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 76 | `K04` | `K01` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 77 | `K05` | `K01` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 78 | `K06` | `K01` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 79 | `K07` | `K01` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 80 | `K08` | `K01` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 81 | `L02` | `L01` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 82 | `L03` | `L01` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 83 | `L04` | `L01` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 84 | `L05` | `L01` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 85 | `L06` | `L01` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 86 | `L07` | `L01` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 87 | `L08` | `L01` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 88 | `M02` | `SK09` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 89 | `M03` | `SK09` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 90 | `M04` | `SK09` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 91 | `M05` | `SK09` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 92 | `M06` | `SK09` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 93 | `M07` | `SK09` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 94 | `M08` | `SK09` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 95 | `SK13` | `N02` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 96 | `N03` | `N02` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 97 | `N04` | `N02` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 98 | `N05` | `N02` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 99 | `N06` | `N02` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 100 | `N07` | `N02` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 101 | `N08` | `N02` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 102 | `O02` | `O01` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 103 | `O03` | `O01` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 104 | `O04` | `O01` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 105 | `O05` | `O01` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 106 | `O06` | `O01` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 107 | `O07` | `O01` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 108 | `O08` | `O01` | `composes_with` | PROPOSED | Cùng domain; kiểm tra ngữ nghĩa và I/O trước khi duyệt |
| 109 | `A08` | `L02` | `composes_with` | PROPOSED | Quan hệ liên miền phục vụ truy xuất; không mặc định cấp quyền/chạy Function |
| 110 | `A06` | `SK03` | `composes_with` | PROPOSED | Quan hệ liên miền phục vụ truy xuất; không mặc định cấp quyền/chạy Function |
| 111 | `A02` | `L01` | `produces_for` | PROPOSED | Quan hệ liên miền phục vụ truy xuất; không mặc định cấp quyền/chạy Function |
| 112 | `A05` | `I07` | `produces_for` | PROPOSED | Quan hệ liên miền phục vụ truy xuất; không mặc định cấp quyền/chạy Function |
| 113 | `SK02` | `D08` | `composes_with` | PROPOSED | Quan hệ liên miền phục vụ truy xuất; không mặc định cấp quyền/chạy Function |
| 114 | `B04` | `G01` | `composes_with` | PROPOSED | Quan hệ liên miền phục vụ truy xuất; không mặc định cấp quyền/chạy Function |
| 115 | `B05` | `B06` | `produces_for` | PROPOSED | Quan hệ liên miền phục vụ truy xuất; không mặc định cấp quyền/chạy Function |
| 116 | `B07` | `A08` | `composes_with` | PROPOSED | Quan hệ liên miền phục vụ truy xuất; không mặc định cấp quyền/chạy Function |
| 117 | `B08` | `L03` | `composes_with` | PROPOSED | Quan hệ liên miền phục vụ truy xuất; không mặc định cấp quyền/chạy Function |
| 118 | `C05` | `I06` | `composes_with` | PROPOSED | Quan hệ liên miền phục vụ truy xuất; không mặc định cấp quyền/chạy Function |
| 119 | `C06` | `C07` | `composes_with` | PROPOSED | Quan hệ liên miền phục vụ truy xuất; không mặc định cấp quyền/chạy Function |
| 120 | `C08` | `G08` | `composes_with` | PROPOSED | Quan hệ liên miền phục vụ truy xuất; không mặc định cấp quyền/chạy Function |
| 121 | `D03` | `A07` | `composes_with` | PROPOSED | Quan hệ liên miền phục vụ truy xuất; không mặc định cấp quyền/chạy Function |
| 122 | `D04` | `D05` | `composes_with` | PROPOSED | Quan hệ liên miền phục vụ truy xuất; không mặc định cấp quyền/chạy Function |
| 123 | `D06` | `C04` | `composes_with` | PROPOSED | Quan hệ liên miền phục vụ truy xuất; không mặc định cấp quyền/chạy Function |
| 124 | `E07` | `K06` | `composes_with` | PROPOSED | Quan hệ liên miền phục vụ truy xuất; không mặc định cấp quyền/chạy Function |
| 125 | `E06` | `L07` | `composes_with` | PROPOSED | Quan hệ liên miền phục vụ truy xuất; không mặc định cấp quyền/chạy Function |
| 126 | `E05` | `I02` | `composes_with` | PROPOSED | Quan hệ liên miền phục vụ truy xuất; không mặc định cấp quyền/chạy Function |
| 127 | `F02` | `G01` | `composes_with` | PROPOSED | Quan hệ liên miền phục vụ truy xuất; không mặc định cấp quyền/chạy Function |
| 128 | `F05` | `SK03` | `composes_with` | PROPOSED | Quan hệ liên miền phục vụ truy xuất; không mặc định cấp quyền/chạy Function |
| 129 | `F04` | `J03` | `composes_with` | PROPOSED | Quan hệ liên miền phục vụ truy xuất; không mặc định cấp quyền/chạy Function |
| 130 | `G04` | `K01` | `produces_for` | PROPOSED | Quan hệ liên miền phục vụ truy xuất; không mặc định cấp quyền/chạy Function |
| 131 | `G05` | `G08` | `produces_for` | PROPOSED | Quan hệ liên miền phục vụ truy xuất; không mặc định cấp quyền/chạy Function |
| 132 | `G02` | `O06` | `produces_for` | PROPOSED | Quan hệ liên miền phục vụ truy xuất; không mặc định cấp quyền/chạy Function |
| 133 | `H04` | `K05` | `produces_for` | PROPOSED | Quan hệ liên miền phục vụ truy xuất; không mặc định cấp quyền/chạy Function |
| 134 | `H07` | `K06` | `composes_with` | PROPOSED | Quan hệ liên miền phục vụ truy xuất; không mặc định cấp quyền/chạy Function |
| 135 | `H08` | `I08` | `composes_with` | PROPOSED | Quan hệ liên miền phục vụ truy xuất; không mặc định cấp quyền/chạy Function |
| 136 | `I01` | `N02` | `composes_with` | PROPOSED | Quan hệ liên miền phục vụ truy xuất; không mặc định cấp quyền/chạy Function |
| 137 | `I06` | `C05` | `composes_with` | PROPOSED | Quan hệ liên miền phục vụ truy xuất; không mặc định cấp quyền/chạy Function |
| 138 | `I04` | `B03` | `composes_with` | PROPOSED | Quan hệ liên miền phục vụ truy xuất; không mặc định cấp quyền/chạy Function |
| 139 | `J01` | `J08` | `produces_for` | PROPOSED | Quan hệ liên miền phục vụ truy xuất; không mặc định cấp quyền/chạy Function |
| 140 | `J02` | `E03` | `composes_with` | PROPOSED | Quan hệ liên miền phục vụ truy xuất; không mặc định cấp quyền/chạy Function |
| 141 | `J05` | `L03` | `composes_with` | PROPOSED | Quan hệ liên miền phục vụ truy xuất; không mặc định cấp quyền/chạy Function |
| 142 | `K05` | `M07` | `produces_for` | PROPOSED | Quan hệ liên miền phục vụ truy xuất; không mặc định cấp quyền/chạy Function |
| 143 | `K06` | `M07` | `produces_for` | PROPOSED | Quan hệ liên miền phục vụ truy xuất; không mặc định cấp quyền/chạy Function |
| 144 | `K02` | `M02` | `produces_for` | PROPOSED | Quan hệ liên miền phục vụ truy xuất; không mặc định cấp quyền/chạy Function |
| 145 | `L02` | `M07` | `produces_for` | PROPOSED | Quan hệ liên miền phục vụ truy xuất; không mặc định cấp quyền/chạy Function |
| 146 | `L08` | `M07` | `composes_with` | PROPOSED | Quan hệ liên miền phục vụ truy xuất; không mặc định cấp quyền/chạy Function |
| 147 | `L05` | `I06` | `produces_for` | PROPOSED | Quan hệ liên miền phục vụ truy xuất; không mặc định cấp quyền/chạy Function |
| 148 | `M03` | `M04` | `produces_for` | PROPOSED | Quan hệ liên miền phục vụ truy xuất; không mặc định cấp quyền/chạy Function |
| 149 | `M02` | `M08` | `produces_for` | PROPOSED | Quan hệ liên miền phục vụ truy xuất; không mặc định cấp quyền/chạy Function |
| 150 | `M06` | `M02` | `composes_with` | PROPOSED | Quan hệ liên miền phục vụ truy xuất; không mặc định cấp quyền/chạy Function |
| 151 | `N03` | `N04` | `produces_for` | PROPOSED | Quan hệ liên miền phục vụ truy xuất; không mặc định cấp quyền/chạy Function |
| 152 | `N08` | `M08` | `composes_with` | PROPOSED | Quan hệ liên miền phục vụ truy xuất; không mặc định cấp quyền/chạy Function |
| 153 | `A06` | `A02` | `depends_on` | PROPOSED | Chỉ chấp nhận dependency cứng nếu contract output/input chứng minh |
| 154 | `B07` | `A08` | `depends_on` | PROPOSED | Chỉ chấp nhận dependency cứng nếu contract output/input chứng minh |
| 155 | `C02` | `C01` | `depends_on` | PROPOSED | Chỉ chấp nhận dependency cứng nếu contract output/input chứng minh |
| 156 | `E07` | `K01` | `depends_on` | PROPOSED | Chỉ chấp nhận dependency cứng nếu contract output/input chứng minh |
| 157 | `K02` | `K01` | `depends_on` | PROPOSED | Chỉ chấp nhận dependency cứng nếu contract output/input chứng minh |
| 158 | `K05` | `K01` | `depends_on` | PROPOSED | Chỉ chấp nhận dependency cứng nếu contract output/input chứng minh |
| 159 | `K07` | `K05` | `depends_on` | PROPOSED | Chỉ chấp nhận dependency cứng nếu contract output/input chứng minh |
| 160 | `L02` | `A08` | `depends_on` | PROPOSED | Chỉ chấp nhận dependency cứng nếu contract output/input chứng minh |
| 161 | `M04` | `M03` | `depends_on` | PROPOSED | Chỉ chấp nhận dependency cứng nếu contract output/input chứng minh |
| 162 | `M08` | `SK09` | `depends_on` | PROPOSED | Chỉ chấp nhận dependency cứng nếu contract output/input chứng minh |
| 163 | `N04` | `N03` | `depends_on` | PROPOSED | Chỉ chấp nhận dependency cứng nếu contract output/input chứng minh |
| 164 | `N07` | `N03` | `depends_on` | PROPOSED | Chỉ chấp nhận dependency cứng nếu contract output/input chứng minh |
| 165 | `L08` | `L01` | `depends_on` | PROPOSED | Chỉ chấp nhận dependency cứng nếu contract output/input chứng minh |
| 166 | `M05` | `SK09` | `depends_on` | PROPOSED | Chỉ chấp nhận dependency cứng nếu contract output/input chứng minh |
| 167 | `O01` | `SK01` | `depends_on` | PROPOSED | Chỉ chấp nhận dependency cứng nếu contract output/input chứng minh |
| 168 | `O01` | `SK02` | `workflow` | PROPOSED | Skill quy trình sử dụng năng lực thành phần; không nhất thiết chạy tất cả |
| 169 | `O01` | `SK03` | `workflow` | PROPOSED | Skill quy trình sử dụng năng lực thành phần; không nhất thiết chạy tất cả |
| 170 | `O01` | `SK04` | `workflow` | PROPOSED | Skill quy trình sử dụng năng lực thành phần; không nhất thiết chạy tất cả |
| 171 | `O01` | `SK05` | `workflow` | PROPOSED | Skill quy trình sử dụng năng lực thành phần; không nhất thiết chạy tất cả |
| 172 | `O01` | `M02` | `workflow` | PROPOSED | Skill quy trình sử dụng năng lực thành phần; không nhất thiết chạy tất cả |
| 173 | `O02` | `B04` | `workflow` | PROPOSED | Skill quy trình sử dụng năng lực thành phần; không nhất thiết chạy tất cả |
| 174 | `O02` | `B05` | `workflow` | PROPOSED | Skill quy trình sử dụng năng lực thành phần; không nhất thiết chạy tất cả |
| 175 | `O02` | `G01` | `workflow` | PROPOSED | Skill quy trình sử dụng năng lực thành phần; không nhất thiết chạy tất cả |
| 176 | `O02` | `G08` | `workflow` | PROPOSED | Skill quy trình sử dụng năng lực thành phần; không nhất thiết chạy tất cả |
| 177 | `O02` | `M02` | `workflow` | PROPOSED | Skill quy trình sử dụng năng lực thành phần; không nhất thiết chạy tất cả |
| 178 | `O03` | `E07` | `workflow` | PROPOSED | Skill quy trình sử dụng năng lực thành phần; không nhất thiết chạy tất cả |
| 179 | `O03` | `K01` | `workflow` | PROPOSED | Skill quy trình sử dụng năng lực thành phần; không nhất thiết chạy tất cả |
| 180 | `O03` | `G01` | `workflow` | PROPOSED | Skill quy trình sử dụng năng lực thành phần; không nhất thiết chạy tất cả |
| 181 | `O03` | `M07` | `workflow` | PROPOSED | Skill quy trình sử dụng năng lực thành phần; không nhất thiết chạy tất cả |
| 182 | `O03` | `M02` | `workflow` | PROPOSED | Skill quy trình sử dụng năng lực thành phần; không nhất thiết chạy tất cả |
| 183 | `O04` | `SK05` | `workflow` | PROPOSED | Skill quy trình sử dụng năng lực thành phần; không nhất thiết chạy tất cả |
| 184 | `O04` | `F02` | `workflow` | PROPOSED | Skill quy trình sử dụng năng lực thành phần; không nhất thiết chạy tất cả |
| 185 | `O04` | `F05` | `workflow` | PROPOSED | Skill quy trình sử dụng năng lực thành phần; không nhất thiết chạy tất cả |
| 186 | `O04` | `M02` | `workflow` | PROPOSED | Skill quy trình sử dụng năng lực thành phần; không nhất thiết chạy tất cả |
| 187 | `O05` | `A02` | `workflow` | PROPOSED | Skill quy trình sử dụng năng lực thành phần; không nhất thiết chạy tất cả |
| 188 | `O05` | `A08` | `workflow` | PROPOSED | Skill quy trình sử dụng năng lực thành phần; không nhất thiết chạy tất cả |
| 189 | `O05` | `D03` | `workflow` | PROPOSED | Skill quy trình sử dụng năng lực thành phần; không nhất thiết chạy tất cả |
| 190 | `O05` | `SK02` | `workflow` | PROPOSED | Skill quy trình sử dụng năng lực thành phần; không nhất thiết chạy tất cả |
| 191 | `O05` | `M02` | `workflow` | PROPOSED | Skill quy trình sử dụng năng lực thành phần; không nhất thiết chạy tất cả |
| 192 | `O06` | `G02` | `workflow` | PROPOSED | Skill quy trình sử dụng năng lực thành phần; không nhất thiết chạy tất cả |
| 193 | `O06` | `G06` | `workflow` | PROPOSED | Skill quy trình sử dụng năng lực thành phần; không nhất thiết chạy tất cả |
| 194 | `O06` | `B04` | `workflow` | PROPOSED | Skill quy trình sử dụng năng lực thành phần; không nhất thiết chạy tất cả |
| 195 | `O06` | `G08` | `workflow` | PROPOSED | Skill quy trình sử dụng năng lực thành phần; không nhất thiết chạy tất cả |
| 196 | `O06` | `M02` | `workflow` | PROPOSED | Skill quy trình sử dụng năng lực thành phần; không nhất thiết chạy tất cả |
| 197 | `O07` | `E03` | `workflow` | PROPOSED | Skill quy trình sử dụng năng lực thành phần; không nhất thiết chạy tất cả |
| 198 | `O07` | `E07` | `workflow` | PROPOSED | Skill quy trình sử dụng năng lực thành phần; không nhất thiết chạy tất cả |
| 199 | `O07` | `K06` | `workflow` | PROPOSED | Skill quy trình sử dụng năng lực thành phần; không nhất thiết chạy tất cả |
| 200 | `O07` | `L08` | `workflow` | PROPOSED | Skill quy trình sử dụng năng lực thành phần; không nhất thiết chạy tất cả |
| 201 | `O07` | `M02` | `workflow` | PROPOSED | Skill quy trình sử dụng năng lực thành phần; không nhất thiết chạy tất cả |
| 202 | `O08` | `A02` | `workflow` | PROPOSED | Skill quy trình sử dụng năng lực thành phần; không nhất thiết chạy tất cả |
| 203 | `O08` | `K05` | `workflow` | PROPOSED | Skill quy trình sử dụng năng lực thành phần; không nhất thiết chạy tất cả |
| 204 | `O08` | `M07` | `workflow` | PROPOSED | Skill quy trình sử dụng năng lực thành phần; không nhất thiết chạy tất cả |
| 205 | `O08` | `L08` | `workflow` | PROPOSED | Skill quy trình sử dụng năng lực thành phần; không nhất thiết chạy tất cả |
| 206 | `O08` | `M02` | `workflow` | PROPOSED | Skill quy trình sử dụng năng lực thành phần; không nhất thiết chạy tất cả |

## Cách dùng cạnh

- `depends_on`: hướng Consumer → Prerequisite; đề xuất chưa tạo phụ thuộc cứng trong runtime.
- `composes_with`: cạnh mềm để retrieval/phối hợp, không tự động gọi Function.
- `workflow`: Skill tổng hợp liên quan các Skill thành phần; không phải execution order.
- `produces_for`: quan hệ cung cấp dữ liệu cần xác minh bằng schema/evidence ports.
- Các cạnh không được dùng để cấp ACL, capability hoặc WRITE permission.
