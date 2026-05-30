MICA GATE PILLAR — LASER CUT SPEC
=================================

Project: Smart gate pillar enclosure (Pi 4 + ESP32 + sensors)
Date:    2026-05-31
File:    mica_gate_pillar.pdf (or .svg)

VẬT LIỆU
--------
Mica acrylic trong suốt, độ dày 3 mm.
Khổ tấm: 800 × 600 mm (1 tấm đủ).

NÉT CẮT vs NÉT KHẮC
-------------------
- Đường màu ĐỎ (RGB 255,0,0):   CẮT THỦNG
- Đường màu ĐEN (RGB 0,0,0):    KHẮC NÔNG (engrave ~0.2mm)

DANH SÁCH 8 CHI TIẾT
--------------------
1. FRONT     150 × 370 mm  (mặt trước)
2. BACK      150 × 400 mm  (mặt sau, có lỗ adapter Ø10mm)
3. LEFT      120 × 400 mm  (ngũ giác, mặt trái)
4. RIGHT     120 × 400 mm  (ngũ giác, mặt phải, có lỗ servo + cảm biến)
5. TOP       150 × 90  mm  (mặt trên, có lỗ LCD 98×40 R4)
6. SLOPE     150 × 42.4 mm (mặt vát 45°, có khắc đánh dấu RFID)
7. BOTTOM    150 × 120 mm  (mặt đáy, có 3 khe thông gió)
8. ARM       150 × 15  mm  (cần chắn)

DUNG SAI
--------
±0.2 mm cho lỗ và mép.
Đường cắt cùng tấm phải canh khoảng cách >= 5mm để tránh vỡ mica.

LƯU Ý
-----
- Nét cắt trong file có độ dày 0.3mm (chỉ để hiển thị PDF); máy laser
  cắt theo đường tâm geometry, không theo độ dày stroke.
- Engrave (vùng RFID trên SLOPE) chỉ cần khắc nông, không cắt thủng.

CẢM ƠN!
