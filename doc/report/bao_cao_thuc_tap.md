# BÁO CÁO THỰC TẬP TỐT NGHIỆP

**Đề tài:** NGHIÊN CỨU, THIẾT KẾ BỘ ĐIỀU KHIỂN CỔNG THU SOÁT VÉ TỰ ĐỘNG AFC TRONG GIAO THÔNG CÔNG CỘNG

**Sinh viên thực hiện:** [HỌ TÊN SINH VIÊN]
**Mã sinh viên:** [MSV]
**Lớp:** [LỚP]
**Khóa:** [KHÓA]
**Đơn vị thực tập:** [ĐƠN VỊ THỰC TẬP]
**Giáo viên hướng dẫn:** [GVHD]
**Khoa:** Điện – Điện tử
**Trường:** Đại học Giao thông vận tải

Hà Nội, năm 2026

---

# LỜI NÓI ĐẦU

Trong xu hướng phát triển mạnh mẽ của Cách mạng công nghiệp 4.0, các hệ thống thu soát vé tự động (AFC – Automatic Fare Collection) đang trở thành thành phần không thể thiếu của hạ tầng giao thông công cộng hiện đại. Tại Việt Nam, sự ra đời của các tuyến đường sắt đô thị (metro) Hà Nội và TP. Hồ Chí Minh cùng các tuyến xe buýt nhanh (BRT) đặt ra yêu cầu cấp thiết về một thế hệ thiết bị cổng AFC tin cậy, đa dạng phương thức xác thực và có khả năng tích hợp dữ liệu về trung tâm điều hành.

Báo cáo thực tập này trình bày quá trình tìm hiểu, phân tích, thiết kế và xây dựng mô hình *Bộ điều khiển cổng thu soát vé tự động AFC* – một mô hình demo cấp prototype, áp dụng kiến trúc **dual-compute** (hai nút tính toán):

- **Raspberry Pi 5** đảm nhiệm khối thị giác máy tính: thu nhận hình ảnh từ webcam USB, nhận diện khuôn mặt, quét mã QR, lưu trữ cơ sở dữ liệu hành khách – vé và cung cấp giao diện web giám sát.
- **ESP32-WROOM-32** đảm nhiệm khối điều khiển ngoại vi thời gian thực: đọc thẻ RFID 13.56 MHz qua module RC522, điều khiển động cơ Servo SG90 đóng/mở cánh chắn, hiển thị trạng thái lên LCD 20×4, phát âm thanh báo hiệu qua buzzer, phát hiện hành khách đi qua bằng cảm biến siêu âm HC-SR04.

Hai khối tính toán giao tiếp qua **một dây cáp USB duy nhất** sử dụng USB-CDC, vận chuyển bản tin JSON Lines ở tốc độ 115200 baud. Việc tắt Wi-Fi trên ESP32 và loại bỏ MQTT giúp đơn giản hóa hệ thống, giảm bề mặt tấn công và tăng độ tin cậy cho mô hình demo.

Báo cáo trình bày đầy đủ các nội dung từ phân tích yêu cầu, lựa chọn công nghệ, thiết kế phần cứng (KiCad), thiết kế cơ khí (FreeCAD), thiết kế phần mềm (Python + Flask trên Pi, Arduino-ESP32 + FreeRTOS trên ESP32), đến kết quả thử nghiệm và hướng phát triển. Đây là tài liệu tổng kết quá trình thực tập của em tại **[ĐƠN VỊ THỰC TẬP]**, đồng thời là cơ sở để mở rộng đề tài thành đồ án tốt nghiệp.

---

# LỜI CAM KẾT

Em xin cam kết báo cáo thực tập tốt nghiệp với đề tài *“Nghiên cứu, thiết kế bộ điều khiển cổng thu soát vé tự động AFC trong giao thông công cộng”* là công trình nghiên cứu của riêng em dưới sự hướng dẫn của thầy/cô **[GVHD]**. Toàn bộ nội dung phân tích, thiết kế, sơ đồ khối, sơ đồ nguyên lý KiCad, bảng phân chân ESP32, lưu đồ thuật toán và kết quả thử nghiệm trình bày trong báo cáo đều do em thực hiện trong quá trình thực tập tại **[ĐƠN VỊ THỰC TẬP]**. Các tài liệu tham khảo được trích dẫn đầy đủ trong mục Tài liệu tham khảo.

Em xin chịu hoàn toàn trách nhiệm về nội dung báo cáo này.

Hà Nội, ngày ___ tháng ___ năm 2026
Sinh viên thực hiện
**[HỌ TÊN SINH VIÊN]**

---

# LỜI CẢM ƠN

Trong suốt quá trình thực tập tốt nghiệp và hoàn thành báo cáo, em đã nhận được rất nhiều sự giúp đỡ tận tình từ thầy cô, đồng nghiệp và bạn bè.

Trước tiên, em xin gửi lời cảm ơn chân thành đến **Ban Chủ nhiệm Khoa Điện – Điện tử**, Trường Đại học Giao thông vận tải đã tạo điều kiện thuận lợi cho em được tham gia kỳ thực tập tốt nghiệp tại doanh nghiệp.

Em xin trân trọng cảm ơn thầy/cô **[GVHD]** – giáo viên hướng dẫn – đã dành nhiều thời gian quý báu để hướng dẫn em từ khâu lựa chọn đề tài, định hình kiến trúc hệ thống, đến việc rà soát kỹ thuật trong từng phần thiết kế phần cứng và phần mềm. Những góp ý sâu sát của thầy/cô về phân bố chân ESP32, giao thức UART JSON Lines và mô hình tác vụ FreeRTOS đã giúp em tránh được nhiều lỗi tiềm ẩn.

Em cũng xin gửi lời cảm ơn đến **[ĐƠN VỊ THỰC TẬP]** đã tiếp nhận, hướng dẫn và tạo điều kiện cho em được tiếp xúc với môi trường làm việc thực tế, được sử dụng các thiết bị (Raspberry Pi 5, ESP32 DevKit DOIT V1 30-pin, module RC522, LCD I2C, Servo SG90, cảm biến HC-SR04, webcam USB) phục vụ cho việc xây dựng mô hình.

Do thời gian thực tập và năng lực còn hạn chế, báo cáo không tránh khỏi những thiếu sót. Em rất mong nhận được sự góp ý của quý thầy/cô và Hội đồng để báo cáo được hoàn thiện hơn.

Em xin chân thành cảm ơn!

Hà Nội, ngày ___ tháng ___ năm 2026
Sinh viên
**[HỌ TÊN SINH VIÊN]**

---

# MỤC LỤC

**LỜI NÓI ĐẦU** ... i
**LỜI CAM KẾT** ... ii
**LỜI CẢM ƠN** ... iii
**DANH MỤC BẢNG BIỂU** ... iv
**DANH MỤC HÌNH VẼ** ... v
**DANH MỤC CÁC CỤM TỪ VIẾT TẮT** ... vi

**CHƯƠNG 1. TỔNG QUAN VỀ HỆ THỐNG THU SOÁT VÉ TỰ ĐỘNG AFC** ... 1
1.1. Giới thiệu hệ thống AFC trong giao thông công cộng ... 1
1.2. Thiết bị cổng trong hệ thống AFC ... 4
1.3. Các công nghệ sử dụng trong thiết bị cổng AFC ... 7
1.4. Các thuật toán điều khiển phổ biến ... 10
1.5. Định hướng và lựa chọn phương án thiết kế cho đồ án ... 13
1.6. Kết luận chương 1 ... 16

**CHƯƠNG 2. THIẾT KẾ PHẦN CỨNG BỘ ĐIỀU KHIỂN CỔNG HỆ THỐNG AFC** ... 17
2.1. Sơ đồ khối tổng thể của hệ thống ... 17
2.2. Lựa chọn thiết bị và linh kiện phần cứng ... 20
2.3. Thiết kế chi tiết phần cứng bộ điều khiển cổng ... 26
2.4. Thiết kế PCB mạch điều khiển và mô hình thiết bị cổng ... 32
2.5. Kết luận chương 2 ... 35

**CHƯƠNG 3. THIẾT KẾ PHẦN MỀM ĐIỀU KHIỂN VÀ XỬ LÝ DỮ LIỆU AFC** ... 36
3.1. Các yêu cầu của phần mềm điều khiển và xử lý dữ liệu ... 36
3.2. Thiết kế cơ sở dữ liệu ... 39
3.3. Thiết kế thuật toán điều khiển ... 43
3.4. Thiết kế giao diện giám sát ... 53
3.5. Kết luận chương 3 ... 56

**CHƯƠNG 4. CÁC KẾT QUẢ THỬ NGHIỆM VÀ ĐÁNH GIÁ** ... 57
4.1. Các sản phẩm của đồ án ... 57
4.2. Các kết quả thử nghiệm sản phẩm ... 60
4.3. Đánh giá sản phẩm ... 65
4.4. Kết luận chương 4 ... 67

**KẾT LUẬN CHUNG** ... 68
**HƯỚNG PHÁT TRIỂN CỦA ĐỀ TÀI** ... 69
**TÀI LIỆU THAM KHẢO** ... 71
**PHỤ LỤC** ... 73

---

# DANH MỤC BẢNG BIỂU

| Bảng | Nội dung |
|---|---|
| Bảng 1.1 | So sánh các loại cổng AFC phổ biến |
| Bảng 1.2 | So sánh các phương thức xác thực vé trong AFC |
| Bảng 1.3 | So sánh các phương án thiết kế đã cân nhắc |
| Bảng 2.1 | Tóm tắt các linh kiện chính của hệ thống |
| Bảng 2.2 | Thông số kỹ thuật Raspberry Pi 5 |
| Bảng 2.3 | Thông số kỹ thuật ESP32-WROOM-32 (DOIT V1 30-pin) |
| Bảng 2.4 | Thông số kỹ thuật module RFID RC522 |
| Bảng 2.5 | Thông số kỹ thuật Servo SG90 |
| Bảng 2.6 | Thông số kỹ thuật cảm biến siêu âm HC-SR04 |
| Bảng 2.7 | Thông số kỹ thuật LCD 20×4 (PCF8574 I2C backpack) |
| Bảng 2.8 | Phân bố chân (Pin assignment) trên ESP32 DOIT V1 30-pin |
| Bảng 2.9 | Ước tính dòng điện tiêu thụ trên các đường nguồn |
| Bảng 3.1 | Danh sách 8 luồng (thread) trong tiến trình Pi 5 |
| Bảng 3.2 | Mô hình tác vụ FreeRTOS trên ESP32 |
| Bảng 3.3 | Bộ động từ lệnh (command verbs) trong giao thức UART |
| Bảng 3.4 | Bộ động từ sự kiện (event verbs) trong giao thức UART |
| Bảng 3.5 | Tổng hợp 20 thuật toán/cấu trúc dữ liệu chính |
| Bảng 4.1 | Kết quả đo độ trễ và tốc độ khung hình nhận diện khuôn mặt |
| Bảng 4.2 | Kết quả đo thời gian đóng/mở cánh chắn |
| Bảng 4.3 | Kết quả 12 kịch bản nghiệm thu firmware ESP32 |
| Bảng 4.4 | Tóm tắt mức đáp ứng yêu cầu thiết kế R1–R14 |

---

# DANH MỤC HÌNH VẼ

| Hình | Nội dung |
|---|---|
| Hình 1.1 | Mô hình tổng quan hệ thống AFC trong giao thông công cộng |
| Hình 1.2 | Quy trình xử lý vé trong hệ thống AFC |
| Hình 1.3 | Các loại cổng AFC: tripod, flap, swing, sliding |
| Hình 1.4 | Quy trình xác thực đa phương thức (Face / QR / RFID) |
| Hình 2.1 | Sơ đồ khối tổng quát hệ thống Smart Gate dual-compute |
| Hình 2.2 | Bo mạch Raspberry Pi 5 và sơ đồ chân |
| Hình 2.3 | Module ESP32 DevKit DOIT V1 30-pin |
| Hình 2.4 | Module RFID RC522 và thẻ Mifare 13.56 MHz |
| Hình 2.5 | Cấu tạo Servo SG90 |
| Hình 2.6 | Nguyên lý hoạt động cảm biến siêu âm HC-SR04 |
| Hình 2.7 | LCD 20×4 với PCF8574 backpack I2C |
| Hình 2.8 | Sơ đồ nguyên lý mạch carrier ESP32 (KiCad) |
| Hình 2.9 | Sơ đồ mạch in (PCB) 2D mặt trước/mặt sau |
| Hình 2.10 | Mô hình 3D PCB carrier |
| Hình 2.11 | Bản vẽ cơ khí khung cổng (FreeCAD) |
| Hình 2.12 | Mô hình lắp ráp thực tế |
| Hình 3.1 | Kiến trúc phần mềm trên Pi 5 (8 luồng) |
| Hình 3.2 | FrameHub fan-out pipeline |
| Hình 3.3 | Sơ đồ quan hệ thực thể (ER) cơ sở dữ liệu SQLite |
| Hình 3.4 | Lưu đồ thuật toán điều khiển tổng thể |
| Hình 3.5 | Lưu đồ thuật toán xử lý RFID |
| Hình 3.6 | Lưu đồ thuật toán quét mã QR |
| Hình 3.7 | Lưu đồ thuật toán nhận dạng khuôn mặt |
| Hình 3.8 | Máy trạng thái cổng (Gate FSM) trên ESP32 |
| Hình 3.9 | Lưu đồ thuật toán chống gian lận |
| Hình 3.10 | Sơ đồ chức năng giao diện giám sát Flask |
| Hình 3.11 | Bố cục dashboard giám sát |
| Hình 4.1 | Hệ thống lắp ráp hoàn thiện |
| Hình 4.2 | Giao diện web admin (dashboard) |
| Hình 4.3 | Sơ đồ kết nối kiểm tra trên bench |

---

# DANH MỤC CÁC CỤM TỪ VIẾT TẮT

| STT | Từ viết tắt | Tiếng Anh | Nghĩa tiếng Việt |
|---|---|---|---|
| 1 | AFC | Automatic Fare Collection | Hệ thống thu vé tự động |
| 2 | AI | Artificial Intelligence | Trí tuệ nhân tạo |
| 3 | API | Application Programming Interface | Giao diện lập trình ứng dụng |
| 4 | BLE | Bluetooth Low Energy | Bluetooth năng lượng thấp |
| 5 | BRT | Bus Rapid Transit | Xe buýt nhanh khối lượng lớn |
| 6 | CCH | Central Clearing House | Trung tâm đối soát giao dịch |
| 7 | CDC | Communications Device Class | Lớp thiết bị truyền thông (USB) |
| 8 | CPU | Central Processing Unit | Bộ xử lý trung tâm |
| 9 | CSI | Camera Serial Interface | Giao tiếp camera nối tiếp |
| 10 | FSM | Finite State Machine | Máy trạng thái hữu hạn |
| 11 | GPIO | General Purpose Input Output | Cổng vào/ra đa năng |
| 12 | HLS | HTTP Live Streaming | Truyền video trực tuyến qua HTTP |
| 13 | I2C | Inter-Integrated Circuit | Bus truyền nối tiếp hai dây |
| 14 | IoT | Internet of Things | Vạn vật kết nối |
| 15 | JSON | JavaScript Object Notation | Định dạng đối tượng JavaScript |
| 16 | LCD | Liquid Crystal Display | Màn hình tinh thể lỏng |
| 17 | LDO | Low-Dropout Regulator | IC ổn áp tuyến tính sụt áp thấp |
| 18 | LED | Light Emitting Diode | Đi-ốt phát quang |
| 19 | LEDC | LED Controller | Bộ điều khiển LED (PWM trên ESP32) |
| 20 | MJPEG | Motion JPEG | Định dạng video chuỗi ảnh JPEG |
| 21 | MQTT | Message Queuing Telemetry Transport | Giao thức truyền tin nhẹ cho IoT |
| 22 | NFC | Near Field Communication | Truyền thông tầm gần |
| 23 | NVS | Non-Volatile Storage | Bộ nhớ không mất khi mất điện |
| 24 | OTA | Over The Air | Cập nhật từ xa qua không dây |
| 25 | PCB | Printed Circuit Board | Bảng mạch in |
| 26 | PWM | Pulse Width Modulation | Điều chế độ rộng xung |
| 27 | QR | Quick Response | Mã phản hồi nhanh |
| 28 | RAM | Random Access Memory | Bộ nhớ truy cập ngẫu nhiên |
| 29 | RFID | Radio Frequency Identification | Nhận dạng tần số vô tuyến |
| 30 | RTOS | Real-Time Operating System | Hệ điều hành thời gian thực |
| 31 | SBC | Single Board Computer | Máy tính nhúng một bo mạch |
| 32 | SoC | System on Chip | Hệ thống trên một chip |
| 33 | SPI | Serial Peripheral Interface | Bus truyền nối tiếp ngoại vi |
| 34 | SQL | Structured Query Language | Ngôn ngữ truy vấn cơ sở dữ liệu |
| 35 | TTL | Transistor-Transistor Logic | Logic mức điện áp transistor |
| 36 | TVM | Ticket Vending Machine | Máy bán vé tự động |
| 37 | UART | Universal Asynchronous Receiver-Transmitter | Truyền thông nối tiếp không đồng bộ |
| 38 | USB | Universal Serial Bus | Bus nối tiếp đa dụng |
| 39 | UVC | USB Video Class | Lớp video chuẩn USB |
| 40 | WAL | Write-Ahead Logging | Chế độ ghi-nhật-ký-trước (SQLite) |

---

# CHƯƠNG 1. TỔNG QUAN VỀ HỆ THỐNG THU SOÁT VÉ TỰ ĐỘNG AFC

## 1.1. Giới thiệu hệ thống AFC trong giao thông công cộng

### 1.1.1. Khái niệm hệ thống AFC

AFC (Automatic Fare Collection – Hệ thống thu vé tự động) là tập hợp các thiết bị, phần mềm và quy trình cho phép thu phí dịch vụ giao thông công cộng (đường sắt đô thị, xe buýt nhanh, phà, bãi gửi xe…) một cách tự động, không cần nhân viên bán/xé vé thủ công. Hệ thống AFC hiện đại đảm nhiệm toàn bộ vòng đời của một giao dịch vé: phát hành – nạp tiền – soát vé tại cổng – ghi nhận giao dịch – đối soát giữa các bên khai thác.

Mục tiêu cốt lõi của AFC bao gồm: rút ngắn thời gian soát vé (target < 1 s/hành khách), giảm chi phí nhân lực, hạn chế gian lận, hỗ trợ đa dạng phương thức thanh toán (thẻ không tiếp xúc, điện thoại NFC, mã QR, sinh trắc khuôn mặt), và cung cấp số liệu thống kê chính xác cho cơ quan quản lý.

### 1.1.2. Vai trò của AFC trong giao thông công cộng

Trong bối cảnh đô thị hóa nhanh tại Hà Nội, TP. Hồ Chí Minh và các thành phố lớn, AFC đóng vai trò không thể thay thế:

1. **Tăng năng lực thông qua (throughput)** của các nút đầu vào trạm metro/BRT: cổng AFC hiện đại đạt 40–60 hành khách/phút, gấp 3–5 lần soát thủ công.
2. **Giảm chi phí vận hành** dài hạn: thay thế hàng chục nhân viên bán/soát vé mỗi ngày bằng một bộ vài chục cổng tự động + bộ phận bảo trì.
3. **Chống thất thoát doanh thu** nhờ ghi nhật ký giao dịch chi tiết, có khả năng đối soát giữa nhà điều hành tuyến và bên thanh toán.
4. **Tạo dữ liệu phục vụ quy hoạch:** dữ liệu thẻ định danh (anonymized) giúp phân tích luồng hành khách, phục vụ tối ưu tuyến và lịch chạy tàu.
5. **Mở đường tích hợp đa phương tiện:** một thẻ duy nhất dùng được cho metro + BRT + bus + bãi gửi xe – mô hình "Mobility as a Service".

Tại Hà Nội, *Quyết định 3680/QĐ-UBND năm 2024* ban hành tiêu chuẩn kỹ thuật cho hệ thống AFC đã định hướng rõ về giao thức trao đổi thẻ (ISO/IEC 14443), độ trễ tối đa khi xác thực, mức ưu tiên giữa các loại thẻ và yêu cầu lưu nhật ký kiểm toán.

### 1.1.3. Kiến trúc hệ thống AFC

Hình 1.1 mô tả kiến trúc tổng quan của một hệ thống AFC hoàn chỉnh, gồm 4 tầng chính:

```
┌──────────── Tầng 1: Thiết bị tại trạm (Station Edge) ──────────┐
│  • Cổng soát vé (Fare Gate / Turnstile)                         │
│  • Máy bán vé tự động (TVM – Ticket Vending Machine)            │
│  • Máy nạp tiền (Add-Value Machine)                             │
│  • Thiết bị POS cầm tay (Hand-held Validator)                   │
└─────────────────────────────┬──────────────────────────────────┘
                              │ Mạng LAN trạm
┌─────────────────────────────┴─────────────────────────────────┐
│       Tầng 2: Trung tâm điều hành trạm (Station Control)       │
│  • Máy chủ kiểm soát truy cập (Station Controller)             │
│  • Cơ sở dữ liệu local cache vé hợp lệ                          │
└─────────────────────────────┬─────────────────────────────────┘
                              │ Mạng WAN
┌─────────────────────────────┴─────────────────────────────────┐
│      Tầng 3: Trung tâm điều hành tuyến (Line Control)          │
│  • Quản lý cấu hình tuyến, đồng bộ giá vé                       │
│  • Tổng hợp giao dịch trong ngày                                │
└─────────────────────────────┬─────────────────────────────────┘
                              │
┌─────────────────────────────┴─────────────────────────────────┐
│   Tầng 4: Trung tâm đối soát giao dịch CCH (Central Clearing) │
│  • Đối soát doanh thu giữa các nhà khai thác                   │
│  • Lưu trữ dài hạn cho kiểm toán (≥ 5 năm)                      │
│  • Cấp phép thẻ định danh, quản lý blacklist                    │
└─────────────────────────────────────────────────────────────────┘
```

**Hình 1.1.** *Mô hình tổng quan hệ thống AFC trong giao thông công cộng.*

Đề tài thực tập tập trung vào **Tầng 1**, cụ thể là *thiết bị cổng soát vé*. Các tầng 2–4 chỉ được đề cập ở mức bối cảnh.

### 1.1.4. Quy trình xử lý vé trong hệ thống AFC

Mỗi giao dịch vé tại cổng AFC tuần tự qua các bước:

1. **Phát hiện hành khách tiếp cận:** cảm biến (hồng ngoại, siêu âm hoặc thị giác máy tính) phát hiện hành khách đến gần đầu đọc.
2. **Áp vé / quét QR / nhận diện khuôn mặt:** hành khách thực hiện hành động xác thực phù hợp với loại vé sở hữu.
3. **Đọc dữ liệu thẻ/QR:** thiết bị đầu đọc gửi dữ liệu (UID thẻ, payload QR, embedding khuôn mặt) đến bộ điều khiển cổng.
4. **Tra cứu local cache:** bộ điều khiển kiểm tra trong cache cục bộ xem vé có hợp lệ, đủ số dư, chưa bị blacklist không.
5. **Quyết định cho qua hay từ chối:** nếu hợp lệ → kích cánh chắn mở; nếu không → hiển thị lý do từ chối (hết hạn, không đủ tiền, thẻ giả…) trên LCD.
6. **Ghi nhật ký giao dịch (transaction log):** bao gồm thời gian, mã thẻ, kết quả, mã trạm, số tiền trừ (nếu có).
7. **Theo dõi hành khách đi qua:** cảm biến vùng trong/ngoài cổng xác nhận hành khách đã thực sự đi qua – đóng cánh chắn ngay sau đó.
8. **Đồng bộ giao dịch về Tầng 2:** định kỳ hoặc real-time, đẩy log giao dịch lên Station Controller, sau đó về CCH.

**Hình 1.2.** *Quy trình xử lý vé trong hệ thống AFC.*

Tổng thời gian từ bước 2 đến bước 6 thường được kỳ vọng ≤ 1 giây để duy trì throughput. Đề tài Smart Gate triển khai một subset đầy đủ của quy trình này (bước 1–7), bỏ bước 8 vì là mô hình demo độc lập.

## 1.2. Thiết bị cổng trong hệ thống AFC

### 1.2.1. Cấu tạo thiết bị cổng AFC

Một thiết bị cổng AFC tiêu chuẩn gồm 4 cụm chính:

- **Cụm cơ khí (mechanical):** khung kim loại, cánh chắn (flap/arm/tripod), động cơ truyền động (Servo/DC motor + encoder), bộ truyền cơ khí (bánh răng hoặc tay đòn).
- **Cụm cảm biến (sensing):** mảng hồng ngoại / siêu âm để phát hiện hành khách vùng "trước-cổng", "trong-cổng" và "sau-cổng"; cảm biến vật cản chống kẹp người.
- **Cụm đầu đọc (reader):** RFID/NFC 13.56 MHz, camera QR, camera khuôn mặt, đầu đọc thẻ ngân hàng tiếp xúc/không tiếp xúc.
- **Cụm điều khiển và hiển thị (control & HMI):** bộ điều khiển trung tâm (PLC/MCU/SBC), LCD hiển thị trạng thái, đèn LED chỉ thị màu xanh-đỏ-vàng, loa hoặc buzzer thông báo.

Tại các tuyến đường sắt đô thị Hà Nội (Cát Linh – Hà Đông, Nhổn – ga Hà Nội), TP. Hồ Chí Minh (Bến Thành – Suối Tiên) và một số tuyến BRT, các nhà cung cấp thiết bị (Thales, Indra, Samsung SDS, Cubic Transportation, GMV, Sancosis…) đang được sử dụng. Đề tài tham khảo nguyên lý chung từ các giải pháp này, không đề cập sản phẩm thương mại cụ thể.

### 1.2.2. Nguyên lý hoạt động

Khi không có hành khách, cánh chắn ở trạng thái OPEN (mặc định cho phép luồng người đi qua – sliding door) hoặc CLOSED (mặc định chặn – flap/tripod). Hai chế độ này được gọi là *normally open* và *normally closed*. Đề tài Smart Gate dùng *normally closed* để bảo đảm an toàn (nếu mất điện thì cổng giữ trạng thái đóng, hành khách không lọt vào miễn phí).

Khi phát hiện hành khách tiếp cận:
- Đầu đọc thẻ/QR/khuôn mặt liên tục quét.
- Nếu xác thực thành công → bộ điều khiển trung tâm gửi lệnh mở cánh chắn → cảm biến chờ hành khách đi qua → đóng cánh chắn ngay.
- Nếu xác thực thất bại → đèn đỏ + thông báo trên LCD + buzzer cảnh báo; cánh chắn giữ nguyên.

Các tình huống an toàn:
- **Hành khách kẹt vào cổng:** cảm biến vùng-trong phát hiện vật cản → cánh chắn không đóng cho đến khi vùng trong sạch.
- **Mở cổng nhưng không đi qua:** sau timeout (5–10 s), cổng tự đóng + cảnh báo.
- **Đi qua không xác thực (tailgate / piggyback):** cảm biến vùng-trong + camera đếm người phát hiện có nhiều hơn 1 người đi qua sau 1 lần mở → trigger alarm.

### 1.2.3. Phân loại các thiết bị cổng

Bảng 1.1 so sánh 4 loại cổng AFC phổ biến trên thị trường (Hình 1.3):

**Bảng 1.1. So sánh các loại cổng AFC phổ biến**

| Loại | Mô tả | Throughput | Ưu điểm | Nhược điểm | Ứng dụng điển hình |
|---|---|---|---|---|---|
| Tripod turnstile | 3 thanh quay 120° | 20–30 ng/ph | Rẻ, đơn giản, bền | Khó qua cho người khuyết tật, hành lý cồng kềnh | Phòng tập, sự kiện, nhà ga nhỏ |
| Flap barrier | 2 cánh nhựa/kính lật ngang | 40–60 ng/ph | Nhanh, sang trọng | Phức tạp, đắt | Metro Hà Nội, TP HCM, văn phòng cao cấp |
| Swing barrier | Cánh quay ngang 90° | 30–40 ng/ph | Cho qua hành lý lớn, xe đẩy | Chiếm diện tích lớn | Sân bay, bệnh viện |
| Sliding barrier | Cánh trượt ngang | 40–50 ng/ph | Đẹp, đóng kín | Cơ khí phức tạp | Khu vực VIP |

**Hình 1.3.** *Các loại cổng AFC: tripod, flap, swing, sliding.*

Đề tài Smart Gate chọn mô hình **barrier-arm (cánh chắn quay 90°)** – tương tự swing barrier nhưng đơn giản hơn (chỉ một cánh, dùng Servo nhỏ). Quyết định này điều chỉnh từ yêu cầu ban đầu trong file `requirement.txt` (đề cập "cửa trượt") bởi vì cánh chắn quay đơn giản về cơ khí, dễ thi công cấp prototype với MDF/acrylic.

### 1.2.4. Yêu cầu kỹ thuật của thiết bị cổng

Một thiết bị cổng AFC để vận hành thực tế cần đáp ứng:

| Yêu cầu | Định lượng |
|---|---|
| Throughput | ≥ 30 hành khách/phút/cổng |
| Thời gian xác thực vé | ≤ 1 s |
| Thời gian mở cánh chắn | ≤ 0.5 s |
| Độ tin cậy (MTBF) | ≥ 50.000 giờ |
| Nhiệt độ làm việc | 0 °C – 50 °C |
| Cấp bảo vệ IP | IP44 (chống bụi và nước bắn) |
| Điện áp cung cấp | 100–240 VAC, 50/60 Hz |
| Tiêu thụ điện | ≤ 60 W trạng thái nghỉ, ≤ 250 W khi đóng/mở |
| Phương thức xác thực | Tối thiểu 2 (thẻ + 1 phương thức khác) |
| Nhật ký giao dịch | Lưu local ≥ 7 ngày, đồng bộ về CCH |
| Tuân thủ tiêu chuẩn | ISO/IEC 14443 (thẻ), EMV (thẻ ngân hàng), ISO 9001 (quản lý chất lượng) |

Đề tài thực tập **không** đặt mục tiêu đạt mức công nghiệp các tiêu chí trên (MTBF, IP44, EMV…) – mô hình demo chỉ mô phỏng nguyên lý.

## 1.3. Các công nghệ sử dụng trong thiết bị cổng AFC

Phần này phân tích các nhóm công nghệ điển hình ứng dụng cho cổng AFC, có liên hệ trực tiếp đến lựa chọn thiết kế của đề tài.

### 1.3.1. Công nghệ RFID/NFC

RFID 13.56 MHz (chuẩn ISO/IEC 14443A) là công nghệ thẻ không tiếp xúc phổ biến nhất trong AFC nhờ:
- Tốc độ giao dịch nhanh (≤ 300 ms).
- Khoảng đọc 3–10 cm phù hợp tự nhiên.
- Hỗ trợ giao dịch mã hóa (Mifare DESFire EV2, EV3).
- Tương thích với hầu hết điện thoại NFC.

Đề tài dùng module RC522 (chip MFRC522 của NXP) đọc thẻ Mifare Classic 1K – là dòng thẻ trắng phổ thông dùng cho mô hình demo.

### 1.3.2. Công nghệ QR Code

Mã QR (Quick Response) cho phép xác thực vé thông qua:
- Vé giấy in QR (single-use, time-limited).
- Vé điện tử hiển thị trên màn hình điện thoại.
- Thẻ thành viên có QR tĩnh.

Ưu điểm của QR so với RFID: chi phí gần như bằng 0 (in giấy), không cần thẻ vật lý chuyên dụng, hỗ trợ bởi mọi smartphone. Nhược điểm: dễ bị copy (cần ký số HMAC + TTL), yêu cầu camera + bộ giải mã.

Đề tài dùng thư viện pyzbar (wrapper Python của libzbar) để giải mã QR trên Pi 5.

### 1.3.3. Công nghệ sinh trắc khuôn mặt

Sinh trắc khuôn mặt (face biometrics) là xu hướng AFC thế hệ mới – đã triển khai tại Trung Quốc (metro Bắc Kinh, Thượng Hải) và một số tuyến châu Âu. Ưu điểm: không cần thẻ vật lý, không cần mang theo điện thoại; nhược điểm: yêu cầu camera chất lượng tốt, dữ liệu sinh trắc nhạy cảm về quyền riêng tư.

Đề tài dùng MediaPipe Face Detection (Google) cho khoanh khuôn mặt và `face_recognition` (wrapper Python của dlib) cho trích xuất embedding 128 chiều.

### 1.3.4. Động cơ và cơ cấu truyền động

Cánh chắn trên cổng AFC công nghiệp thường dùng:
- **Servo motor công suất lớn** (10–20 kg·cm, 24 VDC) với encoder + driver kín kẽ.
- **Stepper motor** (NEMA17/23) cho định vị chính xác.
- **DC motor + bộ truyền giảm tốc** kết hợp encoder quang.

Đề tài chọn **Servo SG90** (1.8 kg·cm) – đủ cho cánh chắn balsa/acrylic 80 mm cấp prototype. Servo SG90 thông dụng, giá rẻ (~30.000 đ), cấp nguồn 5 V, điều khiển bằng PWM 50 Hz.

### 1.3.5. Cảm biến phát hiện hành khách

Các phương án phổ biến:
- **Hồng ngoại khe chắn (through-beam IR):** đơn giản, rẻ; nhưng dễ nhiễu ánh sáng mạnh.
- **Cảm biến siêu âm:** đo khoảng cách thực; ít bị nhiễu ánh sáng; phù hợp môi trường có bụi.
- **Cảm biến laser ToF (Time-of-Flight):** chính xác, đắt.
- **Camera + thị giác máy tính:** đếm người, phát hiện tailgate.

Đề tài chọn **HC-SR04** (siêu âm) thay cho IR như yêu cầu ban đầu trong `requirement.txt`, lý do:
- HC-SR04 trả về khoảng cách thực (cm) thay vì chỉ "có/không".
- Ít bị nhiễu bởi ánh sáng mặt trời và đèn huỳnh quang công suất lớn.
- Cùng giá thành (~30.000 đ), giao tiếp đơn giản (TRIG + ECHO).

### 1.3.6. Bộ điều khiển trung tâm

Các phương án có thể dùng cho bộ điều khiển cổng:
- **PLC công nghiệp** (Siemens, Mitsubishi, Schneider): độ tin cậy cao, đắt.
- **SBC (Linux)** như Raspberry Pi, BeagleBone: linh hoạt, mạnh, có thể chạy AI.
- **MCU** (ESP32, STM32, NXP Kinetis): real-time tốt, tiêu thụ thấp.
- **Kiến trúc kết hợp:** SBC cho vision + MCU cho real-time control.

Đề tài chọn **kiến trúc kết hợp Pi 5 + ESP32** cho mô hình demo – đây là điểm khác biệt chính so với các đồ án sinh viên thường gặp (thường dùng đơn lẻ Pi hoặc đơn lẻ ESP32).

## 1.4. Các thuật toán điều khiển phổ biến

### 1.4.1. Thuật toán xử lý RFID

Quy trình chuẩn cho cổng AFC RFID-only:

```
[Polling RC522 mỗi 50 ms]
    │
    ▼
[IsNewCardPresent()? ──── Không ──▶ tiếp tục polling]
    │ Có
    ▼
[ReadCardSerial() → UID]
    │
    ▼
[Lookup local cache → status]
    │
    ├── Hợp lệ ──▶ [Trừ tiền (nếu cần) → Mở cổng → Ghi log]
    │
    ├── Hết hạn ──▶ [LCD "Expired" + đèn đỏ + buzzer]
    │
    ├── Hết tiền ──▶ [LCD "Insufficient" + đèn đỏ + buzzer]
    │
    └── Không tồn tại / Blacklist ──▶ [LCD "Invalid" + alarm]
    │
    ▼
[HaltA() + StopCrypto1()  ← để thẻ không bị đọc trùng]
    │
    ▼
[Tiếp tục polling]
```

Đề tài đơn giản hóa: chỉ kiểm tra UID có trong NVS allowlist không (không có khái niệm số dư).

### 1.4.2. Thuật toán đọc QR

```
[Capture khung BGR từ webcam]
    │
    ▼
[pyzbar.decode(bgr)]
    │
    ├── Không có QR ──▶ tiếp tục
    │
    ▼ Có
[token = symbol.data.decode('utf-8')]
    │
    ▼
[Verify HMAC (production) hoặc lookup DB (demo)]
    │
    ├── Hợp lệ ──▶ [Mở cổng → Ghi log]
    │
    └── Không hợp lệ ──▶ [Lặng lẽ bỏ qua hoặc ghi attempt]
```

### 1.4.3. Thuật toán nhận dạng khuôn mặt

Một pipeline điển hình:

```
[Capture frame RGB]
    │
    ▼
[Face Detection (MediaPipe / MTCNN / RetinaFace) → bbox]
    │
    ▼
[Crop + align + normalize]
    │
    ▼
[Face Embedding (FaceNet / ArcFace / dlib) → vector 128–512 dim]
    │
    ▼
[Compare với DB embedding bằng cosine similarity hoặc Euclidean distance]
    │
    ├── distance < threshold ──▶ [Grant]
    │
    └── distance ≥ threshold ──▶ [Stranger]
```

Anti-spoofing là bước phụ trợ quan trọng để tránh tấn công bằng ảnh in, video phát lại hoặc mặt nạ 3D. Các kỹ thuật: liveness detection (chớp mắt, quay đầu), texture analysis (moiré pattern), depth sensing (camera stereo).

### 1.4.4. Thuật toán điều khiển cổng

Cổng AFC điển hình dùng máy trạng thái hữu hạn (FSM) gồm 5 trạng thái:

- `IDLE`: cổng đóng, chờ xác thực.
- `OPENING`: cánh chắn đang mở (~300 ms).
- `OPEN_WAIT`: cổng mở, chờ hành khách đi qua (timeout 10 s).
- `TIMEOUT_WARN`: hết timeout chưa thấy đi qua → buzzer cảnh báo (5 s).
- `CLOSING`: cánh chắn đang đóng (~300 ms).

Đề tài triển khai chính xác FSM này trong firmware ESP32 (mục 3.3 và Hình 3.8).

### 1.4.5. Thuật toán chống gian lận

Các pattern gian lận thường gặp tại cổng AFC:
- **Tailgating / piggyback:** 2 người đi sau 1 lần xác thực.
- **Vault jumping:** nhảy qua cánh chắn.
- **Card sharing:** truyền thẻ qua cổng cho người sau.
- **Photo attack:** dùng ảnh in mặt người dùng.

Các thuật toán chống gian lận:
- **Counting beam:** đếm số lần cảm biến chuyển trạng thái – nếu 2 lần "có vật cản" sau 1 lần mở thì cảnh báo.
- **Camera person-counter:** YOLO + tracking đếm số lượng người đi qua.
- **Anti-spoofing biometric:** liveness check.
- **Time-based limit:** thẻ A không được dùng lại trong cùng trạm < N giây.

Đề tài Smart Gate **không** triển khai chống gian lận đầy đủ – đây là một trong các hướng phát triển (mục Hướng phát triển).

## 1.5. Định hướng và lựa chọn phương án thiết kế cho đồ án

### 1.5.1. Mục tiêu nghiên cứu

Mục tiêu của đợt thực tập tốt nghiệp:

1. **Nắm vững kiến trúc dual-compute** trong hệ thống nhúng AFC: hiểu khi nào dùng SBC, khi nào dùng MCU, làm sao để hai bên giao tiếp ổn định.
2. **Thực hành thiết kế đầu-cuối** từ spec đến triển khai: viết tài liệu thiết kế, vẽ sơ đồ khối, phân chân ESP32, vẽ schematic KiCad, mô hình hóa 3D bằng FreeCAD, viết firmware ESP32 (PlatformIO + FreeRTOS), viết ứng dụng Pi (Python + Flask).
3. **Áp dụng các thư viện thị giác máy tính** OpenCV, MediaPipe, face_recognition, pyzbar trong môi trường thực.
4. **Thiết kế giao thức UART** mức ứng dụng: khung tin JSON Lines, bộ động từ lệnh/sự kiện, cơ chế ACK + heartbeat.
5. **Vận dụng FreeRTOS** trên ESP32: tạo task, queue, timer, watchdog.
6. **Quản lý cơ sở dữ liệu** SQLite cho user, face encoding, QR token, transaction log.
7. **Xây dựng giao diện web** giám sát với Flask + HTMX + Pico.css, đủ tối thiểu để demo.
8. **Đánh giá định lượng** hệ thống: độ trễ nhận diện, FPS, thời gian đóng/mở cánh chắn, độ ổn định liên kết UART.

### 1.5.2. Phạm vi đề tài

Phạm vi **bao gồm**:
- Mô hình demo bàn cấp prototype, kích thước ~200 × 100 × 100 mm.
- Một cổng đơn (single gate) với một cánh chắn quay 90°.
- Xác thực 3 phương thức: Face + QR + RFID.
- Cảm biến hành khách đi qua: HC-SR04 siêu âm.
- Giao diện giám sát local: Flask trên Pi 5, truy cập LAN.
- CSDL local: SQLite trên Pi 5.

Phạm vi **không bao gồm**:
- Tích hợp với hệ thống AFC thực tại nhà ga.
- Cloud / multi-gate federation / MQTT broker.
- Anti-spoofing khuôn mặt.
- Authentication trên giao diện web admin.
- Tuân thủ tiêu chuẩn công nghiệp (IP44, EMV, ISO 9001).
- Counting tailgate qua camera.
- Encrypted ticketing (Mifare DESFire EV2/EV3).

### 1.5.3. So sánh các phương án thiết kế

Đề tài đã trải qua 4 phương án thiết kế trước khi chốt phương án cuối:

**Bảng 1.3. So sánh các phương án thiết kế đã cân nhắc**

| Phương án | Mô tả | Ưu điểm | Nhược điểm | Quyết định |
|---|---|---|---|---|
| 1 | ESP32-CAM xử lý tất cả | Đơn giản, 1 board | CPU không đủ chạy face_recognition; PSRAM nhỏ | **Loại** |
| 2 | Pi 5 xử lý tất cả | Mạnh, full Linux | Thiếu PWM phần cứng cho Servo; SPI real-time không an toàn; nếu Pi crash, cánh chắn "đứng" | **Loại** |
| 3 | Pi 5 + ESP32 nối UART rời + Wi-Fi backup | Có dự phòng Wi-Fi | Nhiều đầu nối; phụ thuộc hạ tầng mạng; phức tạp | **Loại** |
| 4 | Pi 5 + ESP32 nối qua 1 dây USB-CDC, NVS allowlist độc lập | Đơn giản nhất; ESP32 hoạt động độc lập | – | **Chọn** |

### 1.5.4. Yêu cầu thiết kế

Bảng yêu cầu R1–R14 (chi tiết kiểm tra ở Chương 4):

| # | Yêu cầu | Tiêu chí kiểm tra |
|---|---|---|
| R1 | Xác thực bằng khuôn mặt | Đúng người trong DB → mở cổng < 2 s |
| R2 | Xác thực bằng QR | Mã hợp lệ → mở cổng < 1 s |
| R3 | Xác thực bằng RFID | Thẻ trong allowlist → mở cổng < 0.5 s |
| R4 | Cánh chắn mở/đóng đúng góc | Mở 100°, đóng 10°, sai số ≤ 5° |
| R5 | Phát hiện hành khách đã qua | HC-SR04 báo trong < 1 s |
| R6 | Cảnh báo nếu không đi qua | Sau 10 s OPEN_WAIT, buzzer warn |
| R7 | Cưỡng bức đóng nếu cảnh báo | Sau 5 s warn, tự đóng |
| R8 | LCD hiển thị tên người dùng | Đúng `"Welcome: <tên>"` khi mở cổng |
| R9 | Ghi sự kiện vào SQLite | Mỗi xác thực → 1 dòng `events`, có `clip_path` |
| R10 | Web admin xem trực tiếp | LAN truy cập `http://<pi>:8080`, thấy MJPEG |
| R11 | Standalone resilience | Rút USB → ESP32 vẫn xác thực RFID + mở/đóng được |
| R12 | Khởi động lại tự động | systemd restart-on-failure |
| R13 | Thi công gọn | Hộp 200 × 100 × 40 mm chứa Pi + carrier ESP32 |
| R14 | Đủ tài liệu | spec, schematic, BOM, README, báo cáo |

## 1.6. Kết luận chương 1

Chương 1 đã giới thiệu tổng quan về hệ thống thu soát vé tự động AFC, vai trò của AFC trong giao thông công cộng và quy trình xử lý vé tại cổng. Các loại thiết bị cổng (tripod, flap, swing, sliding) và các công nghệ cốt lõi (RFID/NFC, QR, sinh trắc khuôn mặt, động cơ Servo, cảm biến) đã được phân tích so sánh, làm cơ sở lựa chọn cho đề tài.

Đề tài Smart Gate hướng đến xây dựng *mô hình demo cấp prototype* của một thiết bị cổng AFC với cánh chắn quay, hỗ trợ 3 phương thức xác thực (Face + QR + RFID). Kiến trúc **dual-compute Pi 5 + ESP32** nối qua một dây USB-CDC đơn giản được chọn sau khi đánh giá 4 phương án – đây là điểm sáng tạo so với các đồ án sinh viên thường dùng đơn lẻ Pi hoặc đơn lẻ ESP32.

Chương tiếp theo (Chương 2) trình bày thiết kế phần cứng chi tiết: sơ đồ khối hệ thống, lựa chọn linh kiện, thiết kế từng khối, PCB carrier ESP32 và mô hình cơ khí cánh chắn.

---

# CHƯƠNG 2. THIẾT KẾ PHẦN CỨNG BỘ ĐIỀU KHIỂN CỔNG HỆ THỐNG AFC

## 2.1. Sơ đồ khối tổng thể của hệ thống

### 2.1.1. Sơ đồ khối tổng quát

Hệ thống Smart Gate được tổ chức thành hai khối tính toán chính (Pi 5 và ESP32) kết nối qua một dây cáp USB-CDC, mỗi khối liên kết với cụm ngoại vi riêng. Hình 2.1 thể hiện sơ đồ khối tổng quát.

```
┌────────────────────── Raspberry Pi 5 ───────────────────────┐
│                                                              │
│  USB Webcam ──▶ V4L2 (/dev/video0) ──▶ cv2.VideoCapture      │
│                                            │                 │
│                                            ▼                 │
│                                       FrameHub               │
│                                            │                 │
│                ┌───────────────┬───────────┴─────────┐       │
│                ▼               ▼                     ▼       │
│         Flask /stream     Detector              RingBuffer   │
│        .mjpeg endpoint   (MediaPipe +          (5s + 5s) →   │
│                          face_recognition       ffmpeg .mp4  │
│                          + pyzbar)                            │
│                ▲               │                              │
│                │               ▼                              │
│        Browser admin    SQLite DB (users,                    │
│        (LAN)            face_encodings,                       │
│                         qr_tokens, events)                    │
│                                                              │
│                  pyserial /dev/ttyUSB0 ◀──── esptool.py      │
└──────────────────────┬───────────────────────────────────────┘
                       │ USB cable (1 sợi, CP2102)
┌──────────────────────┴───────────────────────────────────────┐
│                  ESP32-WROOM-32 DevKit                       │
│                                                              │
│   CP2102 ─── UART0 ─── FreeRTOS tasks:                       │
│              (TX/RX)   - uart_link  (parse + emit JSON)      │
│                        - rfid       (poll RC522 50 ms)       │
│                        - sensor     (HC-SR04 50 ms)          │
│                        - gate_fsm   (state machine)          │
│                                                              │
│   NVS Preferences: authorized UIDs + runtime config          │
│   Wi-Fi: DISABLED                                            │
│                                                              │
│   ┌────────────────────────────────────────────────────┐    │
│   │ Carrier PCB (KiCad-designed):                      │    │
│   │  - RC522 (SPI)                                      │    │
│   │  - LCD 20×4 (I2C)                                   │    │
│   │  - HC-SR04 (TRIG/ECHO + voltage divider)            │    │
│   │  - SG90 servo (LEDC PWM 50 Hz)                      │    │
│   │  - Active buzzer (qua 2N3904)                       │    │
│   │  - Status LED (GPIO 2)                              │    │
│   │  - Đầu vào 12 V DC + buck + LDO                     │    │
│   └────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

**Hình 2.1.** *Sơ đồ khối tổng quát hệ thống Smart Gate dual-compute.*

### 2.1.2. Chức năng từng khối

Bảng tóm tắt vai trò chính:

| Khối | Nền tảng | Chức năng chính |
|---|---|---|
| **Vision** | Pi 5 | Capture webcam, FrameHub fan-out, MediaPipe + face_recognition + pyzbar |
| **Data** | Pi 5 | SQLite WAL (users, face_encodings, qr_tokens, events, esp_log) |
| **Web admin** | Pi 5 | Flask HTTP server, MJPEG live preview, danh sách sự kiện, manual override |
| **Recorder** | Pi 5 | Ring buffer 5s + ffmpeg encode clip MP4 cho mỗi sự kiện |
| **CLI** | Pi 5 | python -m smart_gate.cli (enroll, users, qr, events) |
| **UART link** | Pi 5 ↔ ESP32 | JSON Lines @ 115200 baud, 8 cmd verbs + 6 evt verbs |
| **Real-time control** | ESP32 | 4 FreeRTOS tasks: uart_link, rfid, sensor, gate_fsm |
| **Peripherals** | ESP32 + carrier PCB | RC522 SPI, LCD I2C, Servo SG90 PWM, HC-SR04, buzzer |
| **NVS allowlist** | ESP32 | Preferences-backed UID/name store, max 100 entries |
| **Power** | Carrier PCB | 12 V DC → buck → 5 V → LDO → 3.3 V |
| **Mechanical** | Khung MDF + Servo | Hộp đáy 200×100×40 + 2 trụ 30×30×60 + cánh chắn 80 mm |

### 2.1.3. Phân chia trách nhiệm Pi 5 ↔ ESP32

Pi 5 đảm nhiệm các tác vụ **vision-heavy / non-real-time**:
- Đọc luồng video webcam, encode JPEG.
- Chạy MediaPipe Face Detection (~10 ms/khung).
- Chạy face_recognition embedding (~60–80 ms/khung).
- Chạy pyzbar decode QR (~5 ms/khung).
- Lưu trữ CSDL users, face encodings, QR tokens.
- Cung cấp web admin LAN.
- Ghi video sự kiện qua ffmpeg.

ESP32 đảm nhiệm các tác vụ **real-time / hardware control**:
- Đọc RC522 polling 50 ms/lần.
- Đo HC-SR04 polling 50 ms/lần, debounce 3 lần.
- Phát PWM 50 Hz điều khiển Servo SG90.
- Driver LCD I2C (truyền các text trạng thái).
- Driver buzzer qua 2N3904.
- Lưu danh sách thẻ RFID được phép trong NVS để hoạt động độc lập.

Giao tiếp giữa hai bên qua **giao thức JSON Lines trên USB-CDC** (chi tiết Chương 3 mục 3.3).

## 2.2. Lựa chọn thiết bị và linh kiện phần cứng

### 2.2.1. Tóm tắt linh kiện chính

**Bảng 2.1. Tóm tắt các linh kiện chính của hệ thống**

| Khối | Linh kiện | Vai trò | Số lượng |
|---|---|---|---|
| Tính toán Pi | Raspberry Pi 5 (4 GB hoặc 8 GB) | Vision, web, lưu trữ | 1 |
| Tính toán MCU | ESP32-WROOM-32 (DevKit DOIT V1 30-pin) | Điều khiển ngoại vi | 1 |
| Camera | Webcam USB UVC (Logitech C270) | Thu khuôn mặt + QR | 1 |
| Xác thực thẻ | Module RC522 + thẻ Mifare 13.56 MHz | Đọc UID qua SPI | 1 reader + ≥ 5 thẻ |
| Hiển thị | LCD 20×4 + backpack PCF8574 (I2C) | Hiển thị trạng thái | 1 |
| Cơ cấu chấp hành | Servo SG90 | Quay cánh chắn 0–100° | 1 |
| Cảm biến an toàn | HC-SR04 siêu âm | Phát hiện hành khách | 1 |
| Âm thanh | Active buzzer 5 V | Báo hiệu | 1 |
| Driver buzzer | NPN 2N3904 + R 1 kΩ | Tầng đệm dòng | 1 |
| Nguồn DC | Adapter 12 V / 2 A barrel jack | Cấp cho carrier | 1 |
| Buck | Module MP1584 hoặc LM2596 | 12 V → 5 V | 1 |
| LDO | AMS1117-3.3 | 5 V → 3.3 V | 1 |
| Tụ lọc | 470 µF (3×), 10 µF (2×) | Lọc nguồn | 5 |
| Diode bảo vệ | 1N5819 (anode-side) | Đảo cực bảo vệ | 1 |
| Diode flyback | 1N4148 | Flyback buzzer | 1 |
| Trở | 4.7 kΩ (2×), 1 kΩ (2×), 2 kΩ, 330 Ω | Pull-up I2C, chia áp ECHO, base, LED | 7 |
| Carrier PCB | KiCad 6.0.2 thiết kế | Tích hợp socket DevKit + đầu nối | 1 |
| Khung MDF | 3 mm laser-cut | Hộp đáy + 2 trụ + mặt trước/sau | 1 bộ |
| Cánh chắn | Balsa hoặc acrylic 80×8×3 mm | Quay 0–100° | 1 |
| Giá Servo | PLA in 3D | Gắn SG90 vào trụ | 1 |

### 2.2.2. Raspberry Pi 5

Raspberry Pi 5 (Hình 2.2) là dòng SBC thế hệ mới nhất của Raspberry Pi Foundation, ra mắt cuối 2023. So với Pi 4, Pi 5 dùng SoC Broadcom BCM2712 (4 nhân Cortex-A76 @ 2.4 GHz), GPU VideoCore VII, kèm chip Southbridge tùy chỉnh RP1 (toàn bộ I/O ngoại vi). Pi 5 được chọn (thay vì Pi 4 trong yêu cầu ban đầu) vì hiệu năng CPU/GPU cao hơn ~2–3 lần, đặc biệt quan trọng để chạy face_recognition theo thời gian thực.

**Bảng 2.2. Thông số kỹ thuật Raspberry Pi 5**

| Thông số | Giá trị |
|---|---|
| SoC | Broadcom BCM2712 (4 × Cortex-A76, 2.4 GHz) |
| GPU | VideoCore VII, hỗ trợ OpenGL ES 3.1, Vulkan 1.2 |
| RAM | 4 GB hoặc 8 GB LPDDR4X-4267 |
| Lưu trữ | microSD UHS-I + 1× PCIe 2.0 (cần HAT cho NVMe) |
| USB | 2× USB 3.0 + 2× USB 2.0 |
| Mạng | Gigabit Ethernet, Wi-Fi 5 dual-band, Bluetooth 5.0 |
| Camera | 2× MIPI CSI/DSI (cùng cổng) |
| GPIO | Header 40-pin chuẩn |
| Nguồn | USB-C PD 5 V/5 A (25 W) |

Vai trò trong hệ thống: chạy ứng dụng `smart_gate` (Python 3.11), kết nối webcam qua USB 3.0, kết nối ESP32 qua USB 2.0, kết nối mạng LAN cho web admin.

### 2.2.3. ESP32-WROOM-32 (DevKit DOIT V1 30-pin)

ESP32 (Hình 2.3) là dòng SoC microcontroller của Espressif, ra mắt 2016. Phiên bản classic ESP32-WROOM-32 (Xtensa LX6 dual-core) được chọn vì có sẵn FreeRTOS, đủ GPIO và giá rẻ. DevKit DOIT V1 30-pin là form-factor phổ biến nhất; tích hợp CP2102 USB-UART, nút EN/BOOT, LDO 3.3 V trên-board.

**Bảng 2.3. Thông số kỹ thuật ESP32-WROOM-32 (DOIT V1 30-pin)**

| Thông số | Giá trị |
|---|---|
| CPU | Xtensa LX6 dual-core, 240 MHz |
| RAM | 520 KB SRAM, 16 KB RTC SRAM |
| Flash | 4 MB (trên DevKit chuẩn) |
| Wi-Fi | 802.11 b/g/n (2.4 GHz) – **không dùng trong đề tài** |
| Bluetooth | BT 4.2 Classic + BLE – **không dùng** |
| GPIO | 25 chân khả dụng trên DevKit 30-pin |
| ADC | 18 kênh, 12-bit |
| PWM | LEDC controller, 16 kênh |
| SPI | 4 bộ (SPI0/SPI1 cho flash, HSPI và VSPI cho ứng dụng) |
| I2C | 2 bộ |
| UART | 3 bộ (UART0 cho debug, UART1, UART2) |

DOIT V1 30-pin **không expose** chân GPIO 18/19/21/22/23 (chân SPI/I2C mặc định) → cần dùng GPIO matrix để remap (xem mục 2.3 và Bảng 2.8).

### 2.2.4. Module RFID RC522

Module RC522 (Hình 2.4) dựa trên chip MFRC522 của NXP, làm việc ở 13.56 MHz (ISO/IEC 14443A) với khoảng đọc 3–5 cm cho thẻ Mifare Classic 1K phổ biến.

**Bảng 2.4. Thông số kỹ thuật module RFID RC522**

| Thông số | Giá trị |
|---|---|
| Tần số | 13.56 MHz |
| Giao thức thẻ | ISO/IEC 14443A (Mifare Classic, Ultralight, NTAG) |
| Khoảng đọc | 3–5 cm |
| Giao tiếp MCU | SPI (cũng hỗ trợ I2C/UART tùy module) |
| Điện áp | 3.3 V (không chịu được 5 V) |
| Dòng tiêu thụ | ~26 mA khi đang đọc |

Đề tài dùng UID 4 byte / 7 byte làm khóa primary trong NVS – không đọc nội dung block (đơn giản hóa, không cần authenticate sector).

### 2.2.5. Servo SG90

Servo SG90 (Hình 2.5) là động cơ servo RC nhỏ, phổ biến cho DIY.

**Bảng 2.5. Thông số kỹ thuật Servo SG90**

| Thông số | Giá trị |
|---|---|
| Điện áp | 4.8 – 6.0 V (dùng 5 V) |
| Mô-men xoắn | 1.8 kg·cm @ 4.8 V |
| Tốc độ quay | 60° trong 0.1 s (~300°/s) |
| Góc quay | 0° – 180° (ổn định 10° – 170°) |
| Điều khiển | PWM 50 Hz, độ rộng xung 1.0 – 2.0 ms |
| Dòng tiêu thụ | 100–200 mA; đỉnh ~500 mA tải nặng |

SG90 mô-men 1.8 kg·cm dư cho cánh chắn 80 mm balsa (yêu cầu < 0.3 kg·cm). Đề tài đổi từ MG996R (đề cập trong template) sang SG90 vì cánh chắn nhẹ – tiết kiệm dòng và chi phí (~30.000 đ so với ~150.000 đ).

### 2.2.6. Cảm biến siêu âm HC-SR04

HC-SR04 (Hình 2.6) là cảm biến siêu âm 40 kHz đo khoảng cách bằng thời gian phản hồi xung.

**Bảng 2.6. Thông số kỹ thuật cảm biến siêu âm HC-SR04**

| Thông số | Giá trị |
|---|---|
| Điện áp | 5 V (cần chia áp ECHO xuống 3.3 V cho ESP32) |
| Khoảng đo | 2 cm – 400 cm |
| Độ chính xác | ±3 mm |
| Tần số phát | 40 kHz |
| Dòng tiêu thụ | ~15 mA |
| Giao tiếp | 2 chân: TRIG (input) + ECHO (output) |

**Nguyên lý:**
1. MCU phát xung HIGH 10 µs trên TRIG.
2. Module phát 8 chu kỳ siêu âm 40 kHz.
3. Chân ECHO giữ HIGH trong khoảng thời gian tỉ lệ với khoảng cách: `d (cm) = t (µs) / 58`.
4. ESP32 dùng `pulseIn(PIN_ECHO, HIGH, 30000)` để đo (timeout 30 ms = 5 m).

ECHO ra mức 5 V → cần **chia áp R1 = 1 kΩ + R2 = 2 kΩ** giảm còn 3.3 V cho GPIO 34 (input-only). TRIG nhận 3.3 V vẫn trigger được (ngưỡng HIGH ~3 V).

### 2.2.7. LCD 20×4 (PCF8574 I2C backpack)

LCD 20×4 ký tự (Hình 2.7) – 4 dòng × 20 ký tự – với backpack PCF8574 chuyển từ giao tiếp song song HD44780 sang I2C 4 dây.

**Bảng 2.7. Thông số kỹ thuật LCD 20×4 (PCF8574 I2C backpack)**

| Thông số | Giá trị |
|---|---|
| Kích thước hiển thị | 20 cột × 4 dòng |
| Driver nội | HD44780 |
| Driver backpack | PCF8574 (I2C expander) |
| Địa chỉ I2C | 0x27 (mặc định) hoặc 0x3F |
| Điện áp | VCC 5 V; tín hiệu I2C có thể chạy 3.3 V nếu pull-up về 3.3 V |
| Backlight | LED on/off bằng jumper |
| Tốc độ I2C | 100 kHz (Standard) hoặc 400 kHz (Fast) |

**Vấn đề I2C 5 V:** backpack PCF8574 có pull-up 4.7 kΩ về 5 V → back-drive vào ESP32 3.3 V GPIO. **Giải pháp:** cắt 2 trở pull-up trên backpack, gắn 2 trở 4.7 kΩ về 3.3 V trên carrier PCB.

### 2.2.8. Buzzer và mạch driver

**Active buzzer** (loại có dao động nội bộ): GPIO HIGH → buzzer phát ~2 kHz; GPIO LOW → tắt. Tần số đầu ra cố định bởi mạch dao động trong buzzer, MCU chỉ điều khiển on/off.

Dòng buzzer ~25 mA vượt ngưỡng GPIO ESP32 (12 mA) → cần transistor NPN làm tầng đệm:
- **2N3904** với base resistor 1 kΩ.
- Emitter → GND, Collector → âm buzzer, dương buzzer → 5 V.
- Khi GPIO HIGH (3.3 V), transistor dẫn → buzzer kêu.

### 2.2.9. Khối nguồn

- **Đầu vào:** adapter AC-DC 12 V / 2 A barrel jack 5.5/2.1 mm.
- **Diode bảo vệ 1N5819:** chống đảo cực adapter.
- **Buck MP1584:** 12 V → 5 V, hiệu suất ~85%, dòng đầu ra ≤ 3 A.
- **LDO AMS1117-3.3:** 5 V → 3.3 V, dòng tối đa 1 A (đề tài chỉ cần ~150 mA).
- **Tụ lọc:** C1 470 µF/25 V đầu vào buck, C2 470 µF/16 V đầu ra (gần Servo), C3+C4 10 µF cho LDO.

## 2.3. Thiết kế chi tiết phần cứng bộ điều khiển cổng

Phần này thiết kế từng khối chức năng dẫn đến sơ đồ nguyên lý tổng thể của bo carrier ESP32 (Hình 2.8).

### 2.3.1. Khối nguồn

Sơ đồ khối nguồn:

```
12 V DC ─▶ J1 (barrel jack) ─▶ D1 (1N5819) ─▶ +12V_IN
                                                  │
                                                  ▼
                                          [Buck MP1584]
                                          VIN  EN  VOUT  GND
                                            │   ▲    │
                                            │   │    ├──▶ +5V rail
                                            │  3.3V          │
                                            │ (pull-up)      ├──▶ C2 470 µF
                                            │                │
                                            │                ▼
                                            │           [LDO AMS1117-3.3]
                                            │            VIN  OUT  GND
                                            │              │    │
                                            │              │    ├──▶ +3.3V rail
                                            │              │
                                            └──── C1 470 µF
                                            (đầu vào buck)
```

- **D1 1N5819 Schottky** (Vf ~0.3 V) bảo vệ đảo cực, đặt anode-side đường +12V.
- **C1 470 µF/25 V** lọc nhiễu thấp tần đầu vào buck.
- **Buck MP1584** điều chỉnh xuống 5 V; EN-pin pull-up 10 kΩ về 3.3 V để bật mặc định.
- **C2 470 µF/16 V** đặt sát chân Servo trên rail 5 V để hấp thụ inrush 500 mA của SG90.
- **LDO AMS1117-3.3** chuyển 5 V → 3.3 V cho ESP32 + RC522; tụ C3 (10 µF tantalum) đầu vào, C4 (10 µF) đầu ra.
- Ground topology: ground duy nhất (single-point ground) trên PCB, tránh ground loop.

### 2.3.2. Khối ESP32 socket

ESP32 DevKit DOIT V1 30-pin được cắm vào hai hàng socket header female 15-chân nằm dọc carrier. Đầu cấp nguồn cho DevKit từ rail 5 V của carrier (qua chân VIN của DevKit) – LDO 3.3 V on-board của DevKit sẽ tự cấp 3.3 V cho ESP32, nhưng đề tài **không** dùng nguồn 3.3 V của DevKit cho RC522 (vì dòng ~30 mA của RC522 vượt giới hạn ổn định của LDO trên-board). Thay vào đó, RC522 nhận 3.3 V từ AMS1117 trên carrier.

### 2.3.3. Khối RFID RC522 (SPI)

Sơ đồ kết nối:

```
ESP32 (carrier)                    Module RC522 (J2 header 8-chân)
─────────────                       ─────────────────────────────
GPIO 14 (SCK)    ─────────────────▶ SCK
GPIO 13 (MOSI)   ─────────────────▶ MOSI
GPIO 35 (MISO)   ◀───────────────── MISO
GPIO 15 (CS)     ─────────────────▶ SDA (= CS trên module)
GPIO 4  (RST)    ─────────────────▶ RST
GPIO 16 (IRQ)    ◀───────────────── IRQ (tùy chọn; polling mode)
+3.3V            ─────────────────▶ VCC (3.3V – KHÔNG 5V)
GND              ─────────────────▶ GND
```

Lưu ý:
- Vì DOIT V1 30-pin **không** expose chân SPI mặc định (18/19/21/23), đề tài remap qua GPIO matrix: SCK=14, MOSI=13, MISO=35, CS=15.
- GPIO 35 là input-only → phù hợp cho MISO (luôn input).
- GPIO 15 là strap-HIGH-at-boot → tương thích với CS idle HIGH.
- Tần số SPI: 4 MHz (mặc định MFRC522 library) – thừa cho ứng dụng đọc 13.56 MHz card.

### 2.3.4. Khối LCD 20×4 (I2C)

Sơ đồ kết nối:

```
ESP32              Carrier PCB         LCD 20×4 backpack (J3 4-chân)
─────              ───────────         ──────────────────────────────
GPIO 32 (SDA) ──┬─ R1 4.7kΩ ─ +3.3V    SDA
                │
                └──────────────────▶   SDA
GPIO 33 (SCL) ──┬─ R2 4.7kΩ ─ +3.3V    SCL
                │
                └──────────────────▶   SCL
+5V (rail)    ──────────────────────▶  VCC (5V)
GND           ──────────────────────▶  GND
```

- **Pull-up 4.7 kΩ về 3.3 V** trên carrier (R1, R2) – đảm bảo bus I2C swing đầy đủ giữa 3.3 V và GND.
- **Cắt bỏ pull-up gốc 5 V** trên backpack PCF8574 (note assembly).
- Tần số I2C: 100 kHz (Standard mode) – đủ cho LCD HD44780.

### 2.3.5. Khối HC-SR04

Sơ đồ kết nối:

```
ESP32                              HC-SR04 (J4 4-chân)
─────                              ────────────────────
+5V (rail) ──────────────────────▶ VCC
GND        ──────────────────────▶ GND
GPIO 25 (TRIG)  ─────────────────▶ TRIG (3.3V đủ trigger)
                ┌─── R3 1kΩ ────┐
GPIO 34 (ECHO) ◀┤               │── ECHO (5V output)
   (input-only) │   R4 2kΩ      │
                └───── GND ──────┘
```

- **Chia áp ECHO:** R3 = 1 kΩ + R4 = 2 kΩ giảm ECHO từ 5 V → 5 × (2/3) = 3.33 V.
- TRIG: ESP32 3.3 V trực tiếp đến module – đa số HC-SR04 ngưỡng HIGH ~3 V, hoạt động OK.
- Nếu HC-SR04 không trigger ổn định, có thể thêm BS170 MOSFET làm level shifter (option dự phòng).

### 2.3.6. Khối Servo SG90

Sơ đồ kết nối:

```
ESP32                              SG90 (J5 3-chân)
─────                              ─────────────────
GPIO 26 (PWM) ───────────────────▶ SIG (vàng)
+5V (rail)    ──┬────────────────▶ VCC (đỏ)
                │
                ├─ C2 470 µF/16V ─ GND  (sát chân Servo trên PCB)
                │
GND           ──┴────────────────▶ GND (nâu)
```

- **PWM** từ LEDC kênh 0, tần số 50 Hz, độ rộng xung 1.0 ms (0°) đến 2.0 ms (180°).
- ESP32 3.3 V đủ trigger ngưỡng HIGH của SG90.
- C2 hấp thụ dòng đỉnh 500 mA của SG90 khi bắt đầu quay.

### 2.3.7. Khối Buzzer

Sơ đồ kết nối:

```
+5V ────┬───┬─ Buzzer (+) ──┐
        │   │                │
        │   D2 1N4148        │
        │   (cathode lên)    │
        │   │                │
        │   └────────────┬───┤
                          │
                          ▼
                  Buzzer (–) ─ Collector
                                Q1 2N3904 NPN
GPIO 27 ── R5 1kΩ ── Base
                                Emitter ─ GND
```

- **2N3904 NPN** tầng đệm dòng buzzer 25 mA.
- **R5 = 1 kΩ** giới hạn dòng base.
- **D2 1N4148** flyback bảo vệ khi tắt buzzer (mặc dù active buzzer có dao động nội nên flyback ít cần thiết, vẫn để đề phòng).

### 2.3.8. LED trạng thái

```
GPIO 2 ── R6 330Ω ── LED ── GND
```

LED on-board của DevKit đã có sẵn ở GPIO 2 – đề tài dùng luôn, không cần LED ngoài.

### 2.3.9. Header mở rộng

J6 (6-chân) cho mở rộng tương lai:
- Pin 1: +3.3 V
- Pin 2: GND
- Pin 3: GPIO 17
- Pin 4: GPIO 5
- Pin 5: GPIO 36 (ADC1 capable)
- Pin 6: GPIO 39 (ADC1 capable)

GPIO 12 *không* được bring out vì strap LOW-at-boot.

### 2.3.10. Bảng phân chân ESP32 chi tiết

**Bảng 2.8. Phân bố chân (Pin assignment) trên ESP32 DOIT V1 30-pin**

| GPIO | Hướng | Ngoại vi | Ghi chú |
|---|---|---|---|
| 1 | OUT | UART0 TX (USB-CDC) | Dành riêng |
| 3 | IN | UART0 RX (USB-CDC) | Dành riêng |
| 2 | OUT (strap) | LED trạng thái | Không pull HIGH tại boot |
| 14 | OUT | RC522 SCK | VSPI remap |
| 13 | OUT | RC522 MOSI | VSPI remap |
| 35 | IN-only | RC522 MISO | Input-only OK cho MISO |
| 15 | OUT (strap) | RC522 CS | Strap HIGH OK (CS idle HIGH) |
| 4 | OUT | RC522 RST | Active LOW khi reset |
| 16 | IN | RC522 IRQ | Polling mode không dùng |
| 32 | I/O | LCD I2C SDA | Pull-up 4.7 kΩ về **3.3 V** |
| 33 | OUT | LCD I2C SCL | Pull-up 4.7 kΩ về **3.3 V** |
| 25 | OUT | HC-SR04 TRIG | Xung 10 µs |
| 34 | IN-only | HC-SR04 ECHO | **Phải có chia áp** R1=1k, R2=2k |
| 26 | OUT | Servo SG90 PWM | LEDC kênh 0, 50 Hz |
| 27 | OUT | Active buzzer | Qua 2N3904 + 1 kΩ |
| 6–11 | – | **KHÔNG SỬ DỤNG** | Nối với flash nội |
| 12 | – | **KHÔNG SỬ DỤNG** | Strap LOW at boot |
| 17, 5, 36, 39 | – | Mở rộng | Header J6 |

### 2.3.11. Ước tính dòng tiêu thụ

**Bảng 2.9. Ước tính dòng điện tiêu thụ trên các đường nguồn**

| Đường nguồn | Tải | Dòng đỉnh ước tính |
|---|---|---|
| 3.3 V | ESP32 (120 mA) + RC522 (30 mA) | ~150 mA |
| 5 V | LCD + backlight (50 mA) + HC-SR04 (15 mA) + SG90 (đỉnh 500 mA) + Buzzer (25 mA) | ~600 mA đỉnh |
| 12 V (sau buck ~85% hiệu suất) | (600 mA × 5 V) / (12 V × 0.85) | ~300 mA |

Adapter 12 V/2 A dư so với yêu cầu 300 mA – đảm bảo dự phòng khi thêm ngoại vi.

### 2.3.12. Sơ đồ nguyên lý tổng thể

Sơ đồ nguyên lý đầy đủ được vẽ trong KiCad 6.0.2, lưu tại `kicad/smart_gate_carrier/smart_gate_carrier.kicad_sch` (đơn-sheet). ERC (Electrical Rules Check) đã chạy và clean.

**Hình 2.8.** *Sơ đồ nguyên lý mạch carrier ESP32 (KiCad).*

Sơ đồ tích hợp:
1. ESP32 DevKit socket (2 × 15-pin headers).
2. Khối nguồn (J1 + D1 + MP1584 + AMS1117 + tụ lọc).
3. Khối RC522 (J2 8-chân).
4. Khối LCD (J3 4-chân + pull-up 3.3 V).
5. Khối HC-SR04 (J4 4-chân + chia áp).
6. Khối Servo (J5 3-chân + C2).
7. Khối Buzzer (J7 2-chân + Q1 + R5 + D2).
8. Header mở rộng J6 6-chân.
9. LED status (D3 + R6).

## 2.4. Thiết kế PCB mạch điều khiển và mô hình thiết bị cổng

### 2.4.1. Thiết kế PCB

**Thông số PCB:**
- Kích thước: 80 × 60 mm
- Số lớp: 2 (top + bottom)
- Độ rộng đường tín hiệu: 0.25 mm
- Độ rộng đường nguồn: 0.5 mm
- Via: 0.6/0.3 mm
- Bề mặt: HASL chì hoặc HASL không chì
- Soldermask: xanh (mặc định)
- Silkscreen: trắng

**Bố trí (floorplan):**
- Vùng nguồn (J1, D1, buck, LDO, tụ lọc): góc trái – tách riêng để giảm nhiễu cấp nguồn.
- ESP32 socket: chính giữa – các đầu nối ngoại vi tỏa ra ngoài.
- J2 RC522, J3 LCD, J4 HC-SR04, J5 Servo, J7 Buzzer: bố trí dọc 2 cạnh dài để dễ đi cáp ra ngoài.
- J6 expansion: ở cạnh ngắn.
- LED status: cạnh ngắn còn lại, cùng phía với nút điều khiển.

**Lưu ý layout:**
- Toàn bộ linh kiện chân cắm xuyên lỗ (THT) – không SMD – để dễ hàn tay và sửa.
- Tụ C2 470 µF/16V đặt sát chân Servo, đường +5V đến Servo rộng 1.0 mm để chịu dòng đỉnh 500 mA.
- Đường GND đổ poly fill 2 lớp.
- Khoảng cách tối thiểu giữa các đường: 0.2 mm (theo IPC-2221 cho 25 V); thực tế giữ ≥ 0.3 mm.

**Hình 2.9.** *Sơ đồ mạch in (PCB) 2D mặt trước/mặt sau.*

**Hình 2.10.** *Mô hình 3D PCB carrier.*

(Việc layout PCB là pha tiếp theo của plan KiCad `2026-05-22-kicad-schematic.md`; schematic đã hoàn thành. PCB sẽ tạo từ netlist của schematic.)

### 2.4.2. Mô hình cơ khí thiết bị cổng (FreeCAD)

Mô hình cơ khí được dựng trong FreeCAD 0.21, file `mechanical/smart_gate_assembly.FCStd`.

**Thông số tham số (Spreadsheet):**

| Tham số | Giá trị | Mô tả |
|---|---|---|
| base_w | 200 mm | Rộng thân hộp |
| base_d | 100 mm | Sâu thân hộp |
| base_h | 40 mm | Cao thân hộp |
| post_w | 30 mm | Cạnh trụ |
| post_h | 60 mm | Cao trụ |
| arm_len | 80 mm | Chiều dài cánh chắn |
| lane_w | 60 mm | Rộng lane đi |

**Các chi tiết:**

| Chi tiết | Kích thước (mm) | Vật liệu | Ghi chú |
|---|---|---|---|
| Hộp đáy | 200 × 100 × 40 | MDF 3 mm | Chứa Pi 5 + carrier PCB + buck + cáp |
| Trụ trái (gắn Servo) | 30 × 30 × 60 | MDF 3 mm 6 panel | Servo nằm ngang, horn hướng phải |
| Trụ phải (đỡ) | 30 × 30 × 60 | MDF 3 mm 6 panel | Pad foam đệm khi cánh chắn nghỉ |
| Cánh chắn | 80 × 8 × 3 | Balsa hoặc acrylic | Sơn sọc đỏ/vàng |
| Giá Servo | ~25 × 25 × 25 | PLA in 3D | 2 lỗ M3 cho SG90 |
| Giá camera | dia 8 × 250 + đế 80 × 80 | Cọc gỗ + đế MDF | Nghiêng 30° xuống lane |
| Mặt trước hộp | 200 × 40 | MDF 3 mm | Khoét lỗ LCD 98×24, RC522 60×40, HC-SR04 2×Ø16, LED Ø3, Buzzer Ø8 |
| Mặt sau hộp | 200 × 40 | MDF 3 mm | Lỗ jack DC Ø8, USB-C Pi 14×6, 4 khe tản nhiệt |

**Hình 2.11.** *Bản vẽ cơ khí khung cổng (FreeCAD).*

### 2.4.3. Đầu ra FreeCAD

| File | Loại | Mục đích |
|---|---|---|
| `smart_gate_assembly.FCStd` | Parametric assembly | Top-level, spreadsheet-driven |
| `panels.FCStd` | 2D sketches | Một sketch cho mỗi panel cắt laser, export DXF |
| `servo_bracket.FCStd` | 3D solid | Export STL cho 3D print |
| `arm_coupling.FCStd` | 3D solid (option) | Nếu không gắn cánh trực tiếp lên horn |
| `step_export/*.step` | Auto export | Cho KiCad 3D viewer xác minh PCB vừa khung |

### 2.4.4. Trình tự thi công và lắp ráp

1. Cắt laser các panel MDF từ file DXF (export từ FreeCAD).
2. In 3D giá Servo (PLA, infill 30%, layer 0.2 mm).
3. Gắn SG90 vào giá, gắn giá vào trụ trái bằng vít M3.
4. Gắn cánh chắn vào horn Servo (vít M2 + keo).
5. Đặt PCB carrier đặt sản xuất tại xưởng (gerber export từ KiCad).
6. Hàn linh kiện lên PCB carrier theo BOM.
7. Cắm ESP32 DevKit vào socket carrier, nối ngoại vi qua header XH/Dupont.
8. Cố định carrier PCB và Pi 5 vào đáy hộp bằng cột bằng ốc M2.5.
9. Cắt cửa sổ mặt trước cho LCD, RC522, HC-SR04, LED, buzzer.
10. Gắn webcam lên giá camera; nối cáp USB từ webcam đến cổng USB 3.0 Pi.
11. Nối cáp USB từ Pi đến DevKit ESP32 (cùng cáp dùng cho nạp firmware).
12. Cắm jack DC 12 V vào mặt sau, cấp nguồn carrier.
13. Cấp nguồn USB-C 5 V/5 A cho Pi.

**Hình 2.12.** *Mô hình lắp ráp thực tế.*

## 2.5. Kết luận chương 2

Chương 2 đã trình bày toàn bộ thiết kế phần cứng cho bộ điều khiển cổng AFC Smart Gate, từ sơ đồ khối tổng thể đến chi tiết từng cụm: nguồn 12 V → 5 V → 3.3 V, khối RC522 SPI (remap GPIO matrix), khối LCD I2C 20×4 (pull-up về 3.3 V), khối HC-SR04 (chia áp ECHO), khối Servo SG90 PWM, khối buzzer (đệm 2N3904), khối ESP32 DevKit và header mở rộng.

Phân bố chân ESP32 đã được điều chỉnh phù hợp với DevKit DOIT V1 30-pin (Bảng 2.8) – đây là điểm quan trọng cần lưu ý vì DOIT V1 30-pin không expose chân SPI/I2C mặc định. Ước tính dòng tiêu thụ (Bảng 2.9) cho thấy adapter 12 V/2 A dư so với yêu cầu.

Sơ đồ nguyên lý KiCad đã pass ERC; PCB layout là pha tiếp theo. Mô hình cơ khí FreeCAD parametric với cánh chắn quay 90° bằng MDF + Servo SG90 + giá PLA in 3D đảm bảo demo cấp prototype hoạt động ổn định.

Chương tiếp theo (Chương 3) sẽ trình bày phần thiết kế phần mềm điều khiển và xử lý dữ liệu AFC trên cả Pi 5 và ESP32, bao gồm yêu cầu phần mềm, cơ sở dữ liệu, thuật toán điều khiển và giao diện giám sát.

---

# CHƯƠNG 3. THIẾT KẾ PHẦN MỀM ĐIỀU KHIỂN VÀ XỬ LÝ DỮ LIỆU AFC

## 3.1. Các yêu cầu của phần mềm điều khiển và xử lý dữ liệu

### 3.1.1. Yêu cầu chức năng

Phần mềm Smart Gate phải đáp ứng các yêu cầu chức năng:

1. **Nhận diện vé đa phương thức:**
   - Đọc thẻ RFID 13.56 MHz → tra cứu allowlist → quyết định cho qua/từ chối.
   - Quét mã QR từ webcam → tra cứu DB QR tokens → quyết định.
   - Phát hiện + nhận diện khuôn mặt từ webcam → so khớp với DB face encodings → quyết định.
2. **Kiểm tra tính hợp lệ vé:**
   - Thẻ RFID phải có UID trong allowlist.
   - QR token phải tồn tại trong DB và chưa bị revoked.
   - Embedding khuôn mặt phải gần (Euclidean distance < threshold) với một user trong DB.
3. **Điều khiển cánh chắn:**
   - Khi xác thực thành công, mở cánh chắn (Servo 100°).
   - Khi hành khách đã đi qua, đóng cánh chắn (Servo 10°).
   - Khi xác thực thất bại, không mở.
   - Khi không phát hiện hành khách đi qua sau 10 s, cảnh báo + tự đóng.
4. **Ghi nhật ký giao dịch (transaction log):**
   - Mỗi xác thực (granted hay denied) → 1 dòng trong bảng `events`.
   - Lưu kèm timestamp, phương thức, user_id, kết quả.
   - Lưu clip video sự kiện 10 giây (5 s pre + 5 s post).
5. **Truyền dữ liệu về trung tâm (mô phỏng):**
   - Trong đề tài demo, "trung tâm" là chính máy Pi (local SQLite). Trong production, dữ liệu sẽ truyền qua REST API/MQTT về Station Controller.
6. **Giao diện giám sát:**
   - Web admin LAN xem MJPEG live preview + danh sách sự kiện.
   - Manual override (mở/đóng cổng từ web).
   - Health check.
7. **Quản trị người dùng (CLI):**
   - Enroll user mới với 5 mẫu khuôn mặt + sinh QR token.
   - Liệt kê / xóa user.
   - Rotate / revoke QR token.

### 3.1.2. Yêu cầu phi chức năng

| Tiêu chí | Mục tiêu |
|---|---|
| Độ trễ xác thực RFID | < 500 ms từ áp thẻ đến cổng mở |
| Độ trễ xác thực QR | < 1 s |
| Độ trễ xác thực khuôn mặt | < 2 s |
| FPS detector | ≥ 8 fps |
| Độ chính xác face (≥ 300 lux) | ≥ 90% trong 10 lần thử |
| Tỉ lệ false positive RFID | 0% (UID phải khớp exact) |
| Độ ổn định UART | 0 missed ACK trong 5760 ping (8 giờ liên tục) |
| Khả năng phục hồi | Standalone resilience – ESP32 hoạt động không Pi |
| Khả năng restart | systemd restart-on-failure |
| Quan sát (observability) | Mỗi state transition + lỗi đều phát evt:log |

### 3.1.3. Nền tảng phần cứng và ngôn ngữ lập trình

| Nền tảng | OS / Framework | Ngôn ngữ | Build tool |
|---|---|---|---|
| Raspberry Pi 5 | Raspberry Pi OS Bookworm 64-bit | Python 3.11 | venv + pip |
| ESP32-WROOM-32 | Arduino-ESP32 trên FreeRTOS | C/C++ (Arduino sketch + module .cpp) | PlatformIO |

### 3.1.4. Kiến trúc phần mềm tổng thể

**Trên Pi 5:** một tiến trình Python (`python -m smart_gate`) chạy 8 luồng (Hình 3.1), systemd quản lý lifecycle. Một tiến trình CLI riêng (`python -m smart_gate.cli`) phục vụ enroll/QR/users/events. Đồng bộ giữa daemon và CLI qua SQLite + signal SIGUSR1.

```
systemd: smart-gate.service
    │
    ▼ python -m smart_gate (1 tiến trình, 8 luồng)
    │
    ├── cap          – cv2 V4L2 capture
    ├── detect       – MediaPipe + face_recognition + pyzbar
    ├── rec          – Ring buffer + ffmpeg
    ├── rx           – pyserial reader
    ├── tx           – pyserial writer
    ├── heartbeat    – cmd:ping every 5s
    ├── flask        – werkzeug threaded server
    └── watchdog     – tick monitor threads 1–7
```

**Hình 3.1.** *Kiến trúc phần mềm trên Pi 5 (8 luồng).*

**Bảng 3.1. Danh sách 8 luồng (thread) trong tiến trình Pi 5**

| # | Tên | Module | Vai trò |
|---|---|---|---|
| 1 | cap | video/capture.py | cv2.VideoCapture loop, encode JPEG, publish FrameHub |
| 2 | detect | recognition/detector.py | MediaPipe + face_recognition + pyzbar, phát AuthEvent |
| 3 | rec | video/recorder.py | Ring buffer, ffmpeg encode |
| 4 | rx | link/uart_client.py | Đọc /dev/ttyUSB0, parse JSON, dispatch |
| 5 | tx | link/uart_client.py | Serialize tx_queue → port (single writer) |
| 6 | heartbeat | link/uart_client.py | cmd:ping mỗi 5 s |
| 7 | flask | web/app.py | Werkzeug threaded server bound 0.0.0.0:8080 |
| 8 | watchdog | main.py | Tick-monitor threads 1–7, WARN nếu stale > 30 s |

**Trên ESP32:** firmware Arduino-ESP32 với 4 FreeRTOS task pinned core.

**Bảng 3.2. Mô hình tác vụ FreeRTOS trên ESP32**

| Task | Stack | Priority | Core | Trách nhiệm |
|---|---|---|---|---|
| `uart_link_task` | 4096 B | 3 | 0 | Đọc Serial byte-by-byte, parse JSON, đẩy event_t; drain outbound_q |
| `rfid_task` | 3072 B | 2 | 1 | Polling MFRC522 mỗi 50 ms |
| `sensor_task` | 2048 B | 2 | 1 | Polling HC-SR04 mỗi 50 ms, debounce 3-count |
| `gate_fsm_task` | 4096 B | 4 | 1 | Đọc event_q, chạy FSM, gọi driver Servo/LCD/Buzzer |

Lý do **không** tạo task riêng cho Servo/LCD/Buzzer: các driver này non-blocking (Servo.write() trả về ngay, LCD I2C transaction ~5 ms, buzzer_beep_ok() chỉ 80 ms). Tạo task riêng tốn ~9 KB stack mà không tăng độ phản hồi.

### 3.1.5. Module layout Python

```
smart_gate/
├── __init__.py
├── __main__.py             # entry: python -m smart_gate
├── main.py                 # orchestrator
├── config.py               # tomllib loader + defaults
├── video/
│   ├── capture.py          # cv2 V4L2 thread
│   ├── framehub.py         # threading.Condition fan-out
│   └── recorder.py         # ring buffer + ffmpeg + cleanup
├── recognition/
│   ├── detector.py         # MediaPipe + face_recognition + pyzbar
│   └── matcher.py          # in-memory index, reload on SIGUSR1
├── link/
│   ├── uart_client.py      # rx/tx/heartbeat threads
│   └── protocol.py         # JSON Lines codec (pure functions)
├── web/
│   ├── app.py              # Flask app factory + routes
│   ├── templates/          # base, dashboard, users
│   └── static/             # htmx.min.js, pico.min.css
├── data/
│   ├── db.py               # connection pool
│   ├── models.py           # dataclasses User, Event, FaceEncoding, QrToken
│   └── migrations/0001_init.sql
└── cli/
    ├── enroll.py
    ├── qr.py
    ├── users.py
    └── events.py
```

## 3.2. Thiết kế cơ sở dữ liệu

### 3.2.1. Mô hình dữ liệu

Cơ sở dữ liệu Smart Gate dùng SQLite (chế độ WAL – Write-Ahead Logging) trên Pi 5, gồm 5 bảng:

- **users:** danh sách hành khách đăng ký (định danh sinh trắc + QR; RFID là độc lập).
- **face_encodings:** các vector 128 chiều biểu diễn khuôn mặt của user (mỗi user 3–5 mẫu).
- **qr_tokens:** danh sách QR token đang/đã sử dụng (1 token active/user).
- **events:** nhật ký giao dịch – mỗi xác thực (hợp lệ hay không) là 1 dòng.
- **esp_log:** log từ ESP32 (mirrored từ evt:log).

Sơ đồ quan hệ thực thể (ER):

```
┌─────────────────┐ 1     N ┌──────────────────┐
│ users           │◀────────│ face_encodings   │
│  id (PK)        │         │  id (PK)         │
│  name UNIQUE    │         │  user_id (FK)    │
│  created_at     │         │  embedding BLOB  │
│  last_seen      │         │  sample_idx      │
│  note           │         │  created_at      │
└─────────────────┘         └──────────────────┘
        ▲ 1
        │ N
┌─────────────────┐
│ qr_tokens       │
│  token (PK)     │
│  user_id (FK)   │
│  created_at     │
│  revoked_at     │
└─────────────────┘
        ▲ 0..1
        │ N
┌─────────────────┐
│ events          │
│  id (PK)        │
│  ts             │
│  method         │  -- 'face'|'qr'|'rfid'|'manual_open'|'manual_close'
│  user_id (FK)   │
│  granted        │
│  detail JSON    │
│  clip_path      │
└─────────────────┘

┌─────────────────┐
│ esp_log         │  (đứng độc lập, không khoá ngoại)
│  id (PK)        │
│  ts             │
│  lvl            │
│  tag            │
│  msg            │
└─────────────────┘
```

**Hình 3.3.** *Sơ đồ quan hệ thực thể (ER) cơ sở dữ liệu SQLite.*

### 3.2.2. Schema SQL chi tiết

File `data/migrations/0001_init.sql`:

```sql
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
PRAGMA busy_timeout=5000;

CREATE TABLE users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    last_seen   TEXT,
    note        TEXT
);

CREATE TABLE face_encodings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    embedding   BLOB    NOT NULL,     -- 128 × float32 = 512 byte
    sample_idx  INTEGER NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_face_user ON face_encodings(user_id);

CREATE TABLE qr_tokens (
    token       TEXT    PRIMARY KEY,   -- 32 ký tự hex (16 byte random)
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    revoked_at  TEXT
);
CREATE UNIQUE INDEX idx_qr_active_user
    ON qr_tokens(user_id) WHERE revoked_at IS NULL;

CREATE TABLE events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT    NOT NULL DEFAULT (datetime('now')),
    method      TEXT    NOT NULL,      -- 'face' | 'qr' | 'rfid' | 'manual_open' | 'manual_close'
    user_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    granted     INTEGER NOT NULL,      -- 0 | 1
    detail      TEXT,                  -- JSON
    clip_path   TEXT
);
CREATE INDEX idx_events_ts ON events(ts DESC);

CREATE TABLE esp_log (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    ts   TEXT NOT NULL DEFAULT (datetime('now')),
    lvl  TEXT NOT NULL,                -- 'info' | 'warn' | 'err'
    tag  TEXT,
    msg  TEXT NOT NULL
);
```

### 3.2.3. Các quyết định thiết kế DB

- **3–5 mẫu khuôn mặt/người** (cải thiện độ chính xác khi mặt nghiêng / ánh sáng khác); mỗi mẫu lưu thành 1 dòng. Lookup trả về `min(distance)` qua tất cả mẫu của user.
- **Embedding 128 float32 = 512 byte/dòng**; load `numpy.frombuffer(blob, dtype='float32')`. Toàn bộ ≤ 200 mẫu load vào RAM ngay lúc khởi động.
- **1 QR token active/user** enforce bởi partial unique index `WHERE revoked_at IS NULL`. Rotate = revoke cũ + insert mới trong cùng transaction.
- **Sự kiện RFID** từ ESP32 cũng được mirror vào bảng `events` (`method='rfid'`) để có nhật ký thống nhất – truy vấn nhật ký không cần JOIN nhiều nguồn.
- **Stranger events** (face không match) ghi `user_id=NULL, granted=0`. Debouncer chống spam.
- **`esp_log` tách riêng** từ `events` để log spam không làm lẫn entry history; rotated by row count (giữ 10.000 dòng gần nhất).
- **Index trên `events.ts DESC`** để truy vấn 50 sự kiện gần nhất nhanh.
- **WAL mode** giảm tranh chấp khoá giữa các thread; `busy_timeout=5000` ms phòng deadlock đơn lẻ.

### 3.2.4. Cơ sở dữ liệu trên ESP32 (NVS Preferences)

ESP32 lưu danh sách thẻ RFID được phép trong **NVS namespace `allowlist`**:
- 1 key/UID hex (8 ký tự), value = name (≤ 32 char).
- Key đặc biệt `_index` = JSON array các UIDs, để hỗ trợ `cmd:list_uids` (NVS không có API enumerate cho Preferences keys).
- Giới hạn `ALLOWLIST_MAX_ENTRIES = 100`.

NVS namespace `config`:
- `close_timeout_s` (int) – default 10
- `servo_open_deg` (int) – default 100
- `servo_close_deg` (int) – default 10

Mọi mutation NVS được serialize qua `gate_fsm_task` (single writer) – không cần lock thêm.

### 3.2.5. Luồng dữ liệu toàn hệ thống

```
[Webcam] ──UVC──▶ [Pi 5: cap] ──BGR──▶ [FrameHub]
                                            │
                            ┌───────────────┼─────────────────┐
                            ▼               ▼                  ▼
                     [Flask MJPEG]    [Detector]         [RingBuffer]
                                       │                       │
                                       ▼                       │
                                  [EventBus] ─────────────────▶│
                                       │                       │
                                       ▼                       ▼
                                  [pyserial tx]           [ffmpeg → MP4]
                                       │                       │
                                       ▼                       ▼
                                 /dev/ttyUSB0           data/clips/N.mp4
                                       │
                                       │ ◀──── [pyserial rx] ◀── (evt:rfid, evt:gate, ...)
                                       ▼                              │
                              ┌─────────────┐                          ▼
                              │ ESP32 UART0 │                    [SQLite events]
                              └─────┬───────┘
                                    ▼
                              [uart_link_task]
                                    │
                                    ▼
                              [event_q] ◀─── [rfid_task] ◀─── [RC522]
                                    │   ◀─── [sensor_task] ◀── [HC-SR04]
                                    │   ◀─── [timers]
                                    ▼
                              [gate_fsm_task]
                                    │
                              ┌─────┼────────┬────────┬────────┐
                              ▼     ▼        ▼        ▼        ▼
                          [Servo] [LCD]  [Buzzer]  [LED]  [outbound_q]
                                                              │
                                                              ▼
                                                       [Serial.write JSON\n]
```

## 3.3. Thiết kế thuật toán điều khiển

Phần này trình bày các thuật toán cốt lõi của bộ điều khiển cổng AFC: xử lý RFID, đọc QR, nhận dạng khuôn mặt, điều khiển cánh chắn (FSM) và chống gian lận. Mỗi thuật toán đi kèm phân tích lý thuyết và lưu đồ.

### 3.3.1. Thuật toán điều khiển tổng thể

Lưu đồ tổng thể của bộ điều khiển (Hình 3.4):

```
START → boot system
   │
   ▼
[Pi 5: cap + detect + flask + rx + tx + heartbeat ready]
[ESP32: 4 FreeRTOS tasks + 5 timers ready, emit evt:boot]
   │
   ▼
[Wait: tín hiệu từ một trong 3 nguồn]
   │
   ┌─── Face detection ───┐
   │                       │
   │  ┌── QR detection ──┐ │
   │  │                  │ │
   │  │ ┌─── RFID ───┐   │ │
   │  │ │            │   │ │
   │  │ ▼            │   │ │
   │  │ ESP32 check  │   │ │
   │  │ allowlist    │   │ │
   │  │ │            │   │ │
   │  │ ▼ granted    │   │ │
   │  │ Push event   │   │ │
   │  │ to event_q   │   │ │
   │  │ │            │   │ │
   │  │ ▼            │   │ │
   │  │ Gate FSM ────────────────┐
   │  │ IDLE → OPENING            │
   │  │   → OPEN_WAIT             │
   │  │   → (waiting passage)     │
   │  │                           │
   ▼  ▼  ▼                        │
[Pi 5: matcher.match + debouncer + INSERT event] │
   │                              │
   ▼                              │
[uart.send_cmd("open", ...)]      │
   │                              │
   ▼                              │
[ESP32 uart_link parse,           │
 push EV_CMD_OPEN to event_q] ────┤
                                  ▼
                         [Gate FSM proceeds]
                                  │
                                  ▼
                       [HC-SR04 passage detected?]
                                  │ Yes
                                  ▼
                       [evt:person_passed →
                        Gate FSM → CLOSING → IDLE]
                                  │
                                  ▼
                                LOOP
```

**Hình 3.4.** *Lưu đồ thuật toán điều khiển tổng thể.*

### 3.3.2. Thuật toán xử lý RFID

**Cơ sở lý thuyết:** RFID 13.56 MHz dùng giao thức ISO/IEC 14443A để giao tiếp giữa đầu đọc (PCD – Proximity Coupling Device) và thẻ (PICC – Proximity IC Card). Mỗi thẻ có UID 4 byte hoặc 7 byte cố định khi sản xuất – không đổi được. Đề tài dùng UID làm khóa primary trong NVS allowlist, không đọc nội dung block (đơn giản hóa, không cần authentication key A/B).

**Lưu đồ thuật toán RFID** (Hình 3.5):

```
START (rfid_task, mỗi 50 ms)
   │
   ▼
[mfrc522.PICC_IsNewCardPresent()]
   │
   ├── False ──▶ vTaskDelay(50ms); LOOP
   │
   ▼ True
[mfrc522.PICC_ReadCardSerial()]
   │
   ├── Read fail ──▶ LOGW; LOOP
   │
   ▼ OK
[uid_hex = bytes_to_hex(uid.uidByte, uid.size)]
   │
   ▼
[allowlist_lookup(uid_hex, name_out) → hit?]
   │
   ├── True (granted) ──▶ [event.kind = EV_RFID_SCAN, i1=1, name=name_out]
   │                       Push to event_q
   │                       gate_fsm_task → OPENING (no ack needed)
   │
   └── False (denied) ──▶ [event.kind = EV_RFID_SCAN, i1=0]
                          Push to event_q
                          gate_fsm_task → emit evt:rfid denied + buzzer beep_err
                          (no state transition)
   │
   ▼
[PICC_HaltA() + PCD_StopCrypto1()]   ◀─ tránh đọc trùng khi thẻ giữ trên anten
   │
   ▼
[vTaskDelay(50ms); LOOP]
```

**Hình 3.5.** *Lưu đồ thuật toán xử lý RFID.*

### 3.3.3. Thuật toán đọc QR

**Cơ sở lý thuyết:** Mã QR (Quick Response code, do Denso Wave 1994) là mã matrix 2 chiều có thể chứa tới 4296 ký tự alphanumeric. Mỗi QR gồm 3 ô finder pattern ở 3 góc, các module dữ liệu được mã hóa Reed-Solomon error correction (4 mức: L 7%, M 15%, Q 25%, H 30%). Đề tài dùng thư viện `pyzbar` (wrapper Python của libzbar C library) để decode.

**Thông số:** trung bình 5 ms/khung trên Pi 5; tự xử lý xoay đến 360° và một mức biến dạng nhỏ – không cần preprocess.

**Lưu đồ thuật toán QR** (Hình 3.6):

```
START (detector thread, mỗi khung BGR)
   │
   ▼
[symbols = pyzbar.decode(bgr_frame)]
   │
   ├── Empty? ──▶ Tiếp tục face detection branch
   │
   ▼ Có
For each symbol in symbols:
   │
   ▼
[token = symbol.data.decode('utf-8', errors='replace')]
   │
   ▼
[user_id = matcher.lookup_qr(token)]
   │
   ├── None (token không tồn tại hoặc đã revoked) ──▶ Bỏ qua (no spam log)
   │
   ▼ user_id found
[AuthEvent(method='qr', user_id=..., granted=True)]
   │
   ▼
[Debouncer.should_emit?]
   │
   ├── False (đã grant user này trong < 5s) ──▶ Drop
   │
   ▼ True
[INSERT events(method='qr', user_id=..., granted=1)]
   │
   ▼
[uart.send_cmd('open', {user: name, reason: 'qr'})]
   │
   ▼
[recorder.trigger(event_id)]
   │
   ▼
END (next symbol or next frame)
```

**Hình 3.6.** *Lưu đồ thuật toán quét mã QR.*

QR token trong đề tài đơn giản: 16 byte ngẫu nhiên `secrets.token_hex(16)` = chuỗi 32 ký tự hex. Trong production, sẽ cần kèm HMAC + timestamp + TTL để chống tấn công replay (xem Hướng phát triển).

### 3.3.4. Thuật toán nhận dạng khuôn mặt

**Cơ sở lý thuyết:**

Bài toán nhận dạng khuôn mặt gồm 2 bước:

1. **Phát hiện (face detection):** xác định bbox vị trí khuôn mặt trong khung.
2. **Trích xuất embedding + so khớp (recognition):** chuyển ROI khuôn mặt thành vector số chiều cố định, so sánh với CSDL embedding đã lưu.

Đề tài dùng:
- **Phát hiện:** MediaPipe Face Detection (Google) – ~10 ms/khung trên Pi 5, sử dụng mô hình BlazeFace.
- **Embedding:** `face_recognition` (Adam Geitgey) – wrapper Python của dlib, dùng model `dlib_face_recognition_resnet_model_v1` ResNet-34 đã huấn luyện trên ~3 triệu khuôn mặt – đầu ra vector 128 chiều float32.
- **So khớp:** Euclidean distance trên 128-dim, nearest neighbor.

**Công thức Euclidean distance:**

$$ d(\mathbf{u}, \mathbf{v}) = \sqrt{\sum_{i=1}^{128} (u_i - v_i)^2} $$

Trong code: `numpy.linalg.norm(probe - enc)` – tính trên CPU Pi 5 với 200 vector mất ~1 ms (vectorized).

**Multi-sample matching:**

Mỗi user có 3–5 mẫu chụp ở các góc/biểu cảm khác nhau khi enroll. Khi match:

```python
def match_face(self, probe):
    user_dists = {}
    for user_id, enc in self._faces:
        d = np.linalg.norm(probe - enc)
        if d < user_dists.get(user_id, float('inf')):
            user_dists[user_id] = d
    best_user = min(user_dists, key=user_dists.get) if user_dists else None
    best_dist = user_dists.get(best_user, float('inf'))
    return best_user, best_dist
```

**Ngưỡng quyết định:**

| Khoảng cách | Quyết định |
|---|---|
| d < 0.55 | Grant (cho qua) |
| 0.55 ≤ d ≤ 0.65 | Uncertain (lặng lẽ bỏ qua, chờ khung tốt hơn) |
| d > 0.65 | Stranger (ghi sự kiện granted=0) |

Ngưỡng 0.55 chặt hơn mặc định 0.6 của face_recognition – vì hệ thống demo có base rate thấp (ít người), cần giảm false positive.

**Lưu đồ thuật toán nhận dạng khuôn mặt** (Hình 3.7):

```
START (detector thread, mỗi khung BGR)
   │
   ▼
[Convert BGR → RGB]              (cv2.cvtColor)
   │
   ▼
[MediaPipe Face Detection]
   │
   ├── Không có khuôn mặt ──▶ Return (next frame)
   │
   ▼
[Chọn bbox có score cao nhất]
   │
   ▼
[Pad bbox 20% mỗi chiều, crop ROI]
   │
   ▼
[face_recognition.face_encodings(roi, num_jitters=1)]
   │
   ├── Empty list ──▶ Return
   │
   ▼
[probe = encodings[0].astype('float32')]
   │
   ▼
[matcher.match_face(probe) → (user_id, distance)]
   │
   ├── d < 0.55 ──▶ [granted=True, method='face']
   │                 │
   │                 ▼
   │              [Debouncer.should_emit?]
   │                 │
   │                 ├── False ─▶ Drop (cooldown)
   │                 │
   │                 ▼ True
   │              [INSERT events; uart.send_cmd('open',...)]
   │              [recorder.trigger]
   │                 │
   │                 ▼
   │              END
   │
   ├── 0.55 ≤ d ≤ 0.65 ──▶ Drop silently (uncertain)
   │
   ▼ d > 0.65
[granted=False, user_id=None]
   │
   ▼
[Debouncer.should_emit_stranger?]
   │
   ├── False ──▶ END (cooldown 30s)
   │
   ▼ True
[INSERT events (stranger); recorder.trigger]
   │
   ▼
END
```

**Hình 3.7.** *Lưu đồ thuật toán nhận dạng khuôn mặt.*

### 3.3.5. Quy trình enroll khuôn mặt

CLI `python -m smart_gate.cli enroll --name alice --samples 5`:

1. Mở webcam qua cv2.
2. Hiển thị live preview với bbox khuôn mặt (MediaPipe).
3. Hướng dẫn người dùng nhấn SPACE để chụp 1 mẫu (5 mẫu ở các góc/biểu cảm).
4. Với mỗi mẫu: tính embedding 128-dim, INSERT vào `face_encodings`.
5. Phát signal SIGUSR1 đến daemon → daemon reload matcher.
6. Sinh QR token (16 byte ngẫu nhiên = 32 ký tự hex), INSERT vào `qr_tokens`, ghi PNG vào `data/qr/<name>.png` bằng thư viện `qrcode`.

**So sánh các tùy chọn training:**

| Tùy chọn | Cách làm | Cần GPU |
|---|---|---|
| Google Colab + FaceNet/ArcFace finetune | Train end-to-end | Có |
| OpenCV LBPHRecognizer | Train trên grayscale LBP histogram | Không |
| face_recognition (đã chọn) | Pretrained dlib ResNet-34, chỉ tạo embedding | Không |

Với base rate < 50 người, pretrained embedding đã đủ. Finetune chỉ cần khi dataset người Việt khác biệt rõ với dataset gốc hoặc cần accuracy > 99%.

### 3.3.6. Thuật toán điều khiển cánh chắn (Gate FSM)

**Cơ sở lý thuyết:** Máy trạng thái hữu hạn (Finite State Machine – FSM) gồm 5 trạng thái thể hiện đầy đủ lifecycle của một chu kỳ mở-đóng cổng:

- `IDLE`: trạng thái nghỉ, chờ kích hoạt.
- `OPENING`: cánh chắn đang mở (Servo write 100°, chờ 300 ms).
- `OPEN_WAIT`: cánh chắn mở, chờ hành khách đi qua (timer 10 s).
- `TIMEOUT_WARN`: hết 10 s không thấy đi qua → buzzer cảnh báo (timer 5 s).
- `CLOSING`: cánh chắn đang đóng (Servo write 10°, chờ 300 ms).

**Sơ đồ trạng thái** (Hình 3.8):

```
        ┌──── cmd:open hoặc RFID granted ────┐
        │                                     │
        ▼                                     │
   ┌───────┐  300 ms timer  ┌────────────┐    │
   │ IDLE  │ ──────────────▶│  OPENING   │    │
   └───┬───┘ (phát evt:gate │ (servo PWM │    │
       │  state=opening,    │  → 100°)   │    │
       │  LCD show name,    │            │    │
       │  buzzer beep_ok)   └─────┬──────┘    │
       │                          │           │
       │                          ▼ 300ms     │
       │                  ┌────────────────┐  │
       │                  │  OPEN_WAIT     │  │
       │                  │  10s passage   │  │
       │                  │  timer         │  │
       │                  └─┬────────┬─────┘  │
       │              passage   │     │ 10s   │
       │              detected  │     │ timeout
       │                        │     ▼       │
       │            ┌───────────┘  ┌────────────────┐
       │            │              │ TIMEOUT_WARN   │
       │            │              │ (buzzer warn,  │
       │            │              │  5s give-up)   │
       │            │              └─┬──────┬───────┘
       │            │                │      │
       │            │       passage  │      │ 5s
       │            │       detected │      ▼
       │            ▼                │  ┌────────┐
       │      ┌──────────┐           │  │CLOSING │
       │      │ CLOSING  │ ◀─────────┘  │        │
       │      │ servo PWM│              │        │
       │      │ → 10°    │              │        │
       │      └────┬─────┘              │        │
       │           │ 300ms              │        │
       └───────────┘ ──────────────────▶ IDLE
                                                 
   cmd:close (admin override) ─────────────▶ CLOSING
   cmd:open in OPEN_WAIT ──────▶ reset 10s passage timer (admin hold)
```

**Hình 3.8.** *Máy trạng thái cổng (Gate FSM) trên ESP32.*

**Đặc biệt:**
- SG90 không có feedback vị trí → "Servo đến đích" được giả định sau timer 300 ms (SG90 ≈ 300°/s × 90° ≈ 300 ms).
- `cmd:open` lặp lại trong `OPEN_WAIT` reset bộ đếm 10 s – admin có thể giữ cổng mở cho VIP.
- `cmd:open` trong `OPENING`/`CLOSING` → ack `{ok:false, err:"busy"}`.
- `EV_RFID_SCAN` với i1=0 (denied) trong bất kỳ state → buzzer beep_err + evt:rfid denied, không transition.

### 3.3.7. Thuật toán chống gian lận

Đề tài Smart Gate chỉ triển khai chống gian lận **mức cơ bản** (Hình 3.9):

```
START
   │
   ▼
[Sự kiện xác thực mới đến debouncer]
   │
   ▼
┌─────────────────────────────────┐
│ Kiểm tra cooldown:              │
│ - granted: per-user 5s cooldown │
│ - stranger: 30s global cooldown │
└──────────────┬──────────────────┘
   │
   ├── Trong cooldown ──▶ Drop event (chống spam giữ thẻ liên tục)
   │
   ▼ Past cooldown
[Cập nhật last_grant/last_stranger]
   │
   ▼
[Phát event vào downstream]
   │
   ▼
[ESP32 RC522 PICC_HaltA() + PCD_StopCrypto1()]
   (chỉ ESP32 side – tránh đọc trùng cùng 1 thẻ)
   │
   ▼
END
```

**Hình 3.9.** *Lưu đồ thuật toán chống gian lận cơ bản.*

Các kỹ thuật chống gian lận **chưa** triển khai (xem Hướng phát triển):
- Counting beam đếm tailgate (2 người đi sau 1 lần mở).
- YOLO person-counter qua camera.
- Anti-spoofing khuôn mặt (liveness, depth, texture analysis).
- HMAC + TTL cho QR token (chống replay).

### 3.3.8. Giao thức UART JSON Lines (Pi ↔ ESP32)

**Cấu trúc khung tin:** một bản tin = 1 dòng UTF-8 JSON kết thúc bằng `\n`, tối đa 512 byte.

```json
{"id": 42, "type": "cmd", "v": "open", "data": {"user": "alice", "reason": "face"}}
```

| Trường | Bắt buộc | Ý nghĩa |
|---|---|---|
| `id` | Khi cần ACK | Pi gán số nguyên tăng dần; ESP32 echo lại trong `ack` |
| `type` | Bắt buộc | `"cmd"` / `"evt"` / `"ack"` |
| `v` | Bắt buộc | Verb (động từ) |
| `data` | Tùy verb | Object payload |

Không có CRC (USB-CDC tự lo CRC ở mức USB). Không length-prefix (newline framing đủ). Parser lỗi → drop dòng, tiếp tục.

**Bảng 3.3. Bộ động từ lệnh (cmd) Pi → ESP32**

| Verb | data | ack data | Mục đích |
|---|---|---|---|
| `open` | `{user, reason}` | `{ok:true}` | Pi đã xác thực face/QR; ESP32 mở cổng |
| `close` | – | `{ok:true}` | Cưỡng bức đóng (admin override) |
| `add_uid` | `{uid, name}` | `{ok:true,total:N}` | Thêm UID vào allowlist |
| `remove_uid` | `{uid}` | `{ok:true}` hoặc `{ok:false,err:"not_found"}` | Xóa UID |
| `list_uids` | – | `{uids:[{uid,name},...]}` | Dump allowlist |
| `config` | `{close_timeout_s, servo_open_deg, servo_close_deg}` | `{ok:true}` | Cập nhật cấu hình |
| `status` | – | `{uptime_s, free_heap, gate, fw}` | Snapshot |
| `ping` | – | `{ok:true}` | Liveness probe (Pi gửi mỗi 5 s) |

**Bảng 3.4. Bộ động từ sự kiện (evt) ESP32 → Pi**

| Verb | data | Khi nào |
|---|---|---|
| `boot` | `{fw, free_heap, reset_reason}` | Một lần sau khi các task FreeRTOS sẵn sàng |
| `rfid` | `{uid, result, name?}` | Mỗi lần quét thẻ |
| `gate` | `{state}` | Mỗi chuyển trạng thái FSM |
| `person_passed` | `{distance_cm, ms}` | HC-SR04 phát hiện hành khách đã qua |
| `heartbeat` | `{uptime_s, free_heap, gate}` | Mỗi 10 s |
| `log` | `{lvl, tag, msg}` | Debug messages có rate-limit |

### 3.3.9. Cơ chế ACK và heartbeat

**ACK:** Pi gắn `id` tăng dần vào mỗi `cmd`. ESP32 hồi đáp `{"type":"ack", "id":<id>, "v":<verb>, "data":{...}}` trong < 100 ms. Pi giữ ack_event timer 2 s; quá thời gian → raise `LinkTimeout`.

**Heartbeat:** Pi gửi `cmd:ping` mỗi 5 s; ESP32 phát `evt:heartbeat` mỗi 10 s. Nếu Pi không nhận được message gì từ ESP32 trong 30 s → coi link là dead, đặt `link_alive = False`.

**Standalone resilience:** Khi Pi mất kết nối:
- ESP32 vẫn polling RC522 → xác thực thẻ NVS allowlist → kích FSM tự.
- LCD hiển thị `Welcome: <name>`, cánh chắn mở/đóng bình thường.
- HC-SR04 vẫn phát hiện hành khách đã qua → cổng đóng.
- ESP32 không panic vì thiếu heartbeat Pi.

Khi Pi quay lại:
- Pi nhận `evt:boot` từ ESP32 (nếu ESP32 đã reboot do brownout/lỗi khác).
- Pi gửi `cmd:config` để re-sync runtime params.
- Tiếp tục heartbeat ping mỗi 5 s.

### 3.3.10. Tổng hợp các thuật toán/cấu trúc dữ liệu

**Bảng 3.5. Tổng hợp 20 thuật toán/cấu trúc dữ liệu chính**

| # | Thuật toán | Triển khai | Vai trò |
|---|---|---|---|
| 1 | MediaPipe Face Detection | `mp.solutions.face_detection.FaceDetection` | Khoanh khuôn mặt |
| 2 | dlib face_recognition_model_v1 | `face_recognition.face_encodings` | Embedding 128-dim |
| 3 | Euclidean distance + nearest neighbor | `numpy.linalg.norm` + dict argmin | Match user |
| 4 | Multi-sample min-distance | for-loop trong matcher | Cải thiện accuracy |
| 5 | Threshold + uncertain band | `if d < 0.55: grant elif d > 0.65: stranger` | Giảm false positive |
| 6 | pyzbar libzbar wrapper | `pyzbar.decode(bgr)` | Decode QR |
| 7 | Debounce cooldown | `if now - last_grant[uid] < 5: skip` | Tránh trigger trùng |
| 8 | FrameHub fan-out | `threading.Condition.notify_all` | 3 consumers / 1 source |
| 9 | RingBuffer 5s | `collections.deque(maxlen=fps*5)` | Lưu khung pre-event |
| 10 | ffmpeg H.264 encode | `subprocess.run([...])` | MP4 clip 10s |
| 11 | JSON Lines framing | `json.dumps + "\n".encode("utf-8")` | UART protocol |
| 12 | UART exponential backoff | `1, 2, 5, 10, 30 s` | Robust port handling |
| 13 | HC-SR04 debounce 3-count | `below_count` / `above_count` | Lọc nhiễu |
| 14 | FreeRTOS xTimer one-shot | `xTimerCreate(..., pdFALSE, ...)` | Servo settle, timeout, warn |
| 15 | FreeRTOS xQueue | `xQueueCreate(16, sizeof(event_t))` | Inter-task event passing |
| 16 | TWDT watchdog | `esp_task_wdt_add(gate_fsm_task)` | Auto-reboot nếu FSM stall |
| 17 | NVS Preferences `_index` sidecar | Self-maintained JSON array | Enumerate allowlist |
| 18 | Rate-limited log | 1 evt:log/s per (lvl, tag) | Tránh flood UART |
| 19 | LEDC PWM 50 Hz Servo | `ledc_set_duty(channel0)` | Servo control |
| 20 | I2C 100 kHz LCD | `Wire.begin(SDA, SCL); lcd.begin()` | LCD HD44780 qua PCF8574 |

## 3.4. Thiết kế giao diện giám sát

Đề tài chọn **Flask** (Python micro-framework) chạy trên Pi 5 cho web admin LAN, không có web admin trên ESP32 (do Wi-Fi ESP32 đã tắt theo phương án thiết kế).

### 3.4.1. Sơ đồ chức năng giao diện

```
                    Browser (LAN, không có authentication)
                              ▲
                              │ HTTP/HTTPS
                              ▼
                    ┌──────────────────────┐
                    │  Werkzeug threaded   │
                    │  server :8080        │
                    │  (Flask 3.0.3)       │
                    └────────┬─────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Routes:     │    │  Routes:     │    │  Routes:     │
│  /           │    │  /api/gate/  │    │  /events.json│
│  /stream     │    │  open|close  │    │  /clips/N.mp4│
│  /users      │    │  (manual     │    │  /healthz    │
│              │    │   override)  │    │              │
└──────┬───────┘    └──────┬───────┘    └──────┬───────┘
       │                   │                   │
       ▼                   ▼                   ▼
   FrameHub          UartClient          SQLite DB
   wait_jpeg()       send_cmd()          query events
```

**Hình 3.10.** *Sơ đồ chức năng giao diện giám sát Flask.*

### 3.4.2. Các route Flask

| URL | Phương thức | Chức năng |
|---|---|---|
| `/` | GET | `dashboard.html` – trang chính |
| `/stream.mjpeg` | GET | `multipart/x-mixed-replace` MJPEG generator từ FrameHub.wait_jpeg() |
| `/events.json?after_id=N` | GET | JSON list 50 sự kiện gần nhất (HTMX polling 2s) |
| `/users` | GET | Bảng user, số mẫu face, QR active |
| `/clips/<int:event_id>.mp4` | GET | `send_file()` từ data/clips/; 404 nếu clip_path NULL |
| `/api/gate/open` | POST | `uart.send_cmd("open", {user:"admin",reason:"manual"}, 2.0)` |
| `/api/gate/close` | POST | `uart.send_cmd("close", None, 2.0)` |
| `/healthz` | GET | `{uptime_s, link_alive, last_frame_ago_s, threads_ok}` |

Templates Jinja2 + HTMX (`/static/htmx.min.js` ~14 KB) polling `/events.json` mỗi 2 s. Pico.css (~10 KB) cho style baseline. Không SPA framework. Không auth (LAN-only).

### 3.4.3. Bố cục dashboard

```
┌────────────────────────────────┬──────────────────────────────┐
│   [HỌ TÊN SVTH]  –  [MSV]      │  Events (hx-trigger=every 2s)│
│   Smart Gate Dashboard          │  ┌─────┬──────┬────────┐    │
├────────────────────────────────┤  │ time│ user │ method │    │
│                                │  ├─────┼──────┼────────┤    │
│   <img src="/stream.mjpeg">    │  │ ... │  ... │  ...   │    │
│   (640×480 MJPEG live)         │  │ ... │  ... │  ...   │    │
│                                │  └─────┴──────┴────────┘    │
│   [ Open gate ] [ Close gate ] │                              │
│   Link: ● up   Frame: 0.2s ago │                              │
├────────────────────────────────┴──────────────────────────────┤
│   Footer: GVHD: [GVHD]  –  Lớp [LỚP]  –  Khoá [KHÓA]          │
└────────────────────────────────────────────────────────────────┘
```

**Hình 3.11.** *Bố cục dashboard giám sát.*

Dashboard hiển thị:
- Tên sinh viên + MSV ở header (theo yêu cầu trong template `cơ bản.docx`).
- MJPEG live preview 640×480.
- Bảng sự kiện gần nhất (cập nhật mỗi 2 s).
- Nút Open/Close gate (manual override).
- Thông tin link và frame age.

### 3.4.4. MJPEG stream generator

```python
def mjpeg_stream():
    while True:
        jpg = hub.wait_jpeg(timeout=2.0)
        if jpg is None:
            jpg = PLACEHOLDER_JPEG  # "Camera offline" ~3 KB
        yield (b"--FRAME\r\nContent-Type: image/jpeg\r\n"
               b"Content-Length: " + str(len(jpg)).encode() + b"\r\n\r\n"
               + jpg + b"\r\n")
```

Mỗi khung mới do FrameHub broadcast được serialize thẳng đến browser qua HTTP multipart. Browser native render qua `<img src="/stream.mjpeg">` – không cần JS player.

### 3.4.5. CLI quản trị

`python -m smart_gate.cli <subcommand>`:

| Subcommand | Chức năng |
|---|---|
| `enroll --name X --samples 5` | Capture 5 mẫu khuôn mặt + sinh QR + INSERT DB |
| `users list` | Bảng user, created_at, last_seen, #encodings, #qr active |
| `users delete --name X` | DELETE FROM users WHERE name=? (CASCADE) |
| `qr rotate --name X` | Revoke old + insert new token + rewrite PNG |
| `qr revoke --name X` | UPDATE qr_tokens SET revoked_at=now() |
| `events tail -n 20` | SELECT ... ORDER BY ts DESC LIMIT 20 |
| `db migrate` | Apply migrations idempotently |

CLI tách riêng tiến trình daemon → an toàn khi chạy đồng thời nhờ SQLite WAL + busy_timeout. Sau mỗi mutation, CLI gửi `SIGUSR1` đến PID daemon (`/run/smart-gate/pid`) để matcher reload.

## 3.5. Kết luận chương 3

Chương 3 đã trình bày toàn bộ thiết kế phần mềm điều khiển và xử lý dữ liệu AFC, từ yêu cầu chức năng/phi chức năng, kiến trúc 8-luồng Pi 5 + 4-task ESP32, mô hình dữ liệu SQLite WAL 5 bảng, đến chi tiết 5 thuật toán cốt lõi (RFID, QR, face recognition, gate FSM, anti-fraud) đi kèm lưu đồ thuật toán. Giao thức UART JSON Lines giữa Pi và ESP32 đặc tả 8 cmd verbs + 6 evt verbs với cơ chế ACK + heartbeat đảm bảo độ tin cậy. Giao diện Flask LAN cung cấp MJPEG live preview, bảng sự kiện và manual override.

Hệ thống được thiết kế với các nguyên tắc:
- **Tách trách nhiệm** rõ ràng giữa Pi (vision) và ESP32 (real-time).
- **Đơn giản hóa**: 8 luồng Pi + 4 task ESP32 – không phình to.
- **Quan sát**: mọi state transition + lỗi đều phát evt:log.
- **Cấu hình hóa**: tham số runtime đều chỉnh qua `config.toml` hoặc `cmd:config`.
- **Phục hồi**: ESP32 hoạt động độc lập với RFID khi Pi mất kết nối.

Chương tiếp theo (Chương 4) trình bày các sản phẩm thực tế, kịch bản thử nghiệm, kết quả đo đạc và đánh giá.

---

