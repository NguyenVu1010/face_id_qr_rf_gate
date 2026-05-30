MICA GATE PILLAR — LASER CUT SPEC
=================================

Project: Smart gate pillar enclosure (Pi 4 + ESP32 + sensors)
Date:    2026-05-31
File:    mica_gate_pillar.pdf (or .svg)

VẬT LIỆU
--------
Mica acrylic trong suốt, độ dày 5 mm.
Khổ tấm: 1000 × 600 mm (1 tấm đủ).

NÉT CẮT vs NÉT KHẮC
-------------------
- Đường màu ĐỎ (RGB 255,0,0):   CẮT THỦNG
- Đường màu ĐEN (RGB 0,0,0):    KHẮC NÔNG (engrave ~0.2mm)

DANH SÁCH 8 CHI TIẾT
--------------------
1. FRONT     150 × 228 mm  (mặt trước)
2. BACK      150 × 300 mm  (mặt sau, có lỗ adapter Ø10mm)
3. LEFT      240 × 300 mm  (ngũ giác, mặt trái)
4. RIGHT     240 × 300 mm  (ngũ giác, mặt phải, có khe arm 20×130mm + cảm biến; servo dời vào trong)
5. TOP       150 × 168 mm  (mặt trên, có lỗ LCD 98×40 R4)
6. SLOPE     150 × 101.8 mm (mặt vát 45°, có khắc đánh dấu RFID)
7. BOTTOM    150 × 240 mm  (mặt đáy, có 5 khe thông gió)
8. ARM       195 × 15  mm  (cần chắn — có khắc 5 vạch sọc 20mm × 5mm — sau khi cắt sơn ĐỎ vào các vạch khắc để giả barrier sọc đỏ-trắng)

DUNG SAI
--------
±0.2 mm cho lỗ và mép.
Đường cắt cùng tấm phải canh khoảng cách >= 5mm để tránh vỡ mica.

LƯU Ý
-----
- Nét cắt trong file có độ dày 0.3mm (chỉ để hiển thị PDF); máy laser
  cắt theo đường tâm geometry, không theo độ dày stroke.
- Engrave (vùng RFID trên SLOPE và 5 vạch sọc trên ARM) chỉ cần khắc nông, không cắt thủng.

CẢM ƠN!
