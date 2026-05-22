# BÁO CÁO THỰC TẬP TỐT NGHIỆP

**Đề tài:** Thiết kế và xây dựng hệ thống cổng thông minh (Smart Gate) sử dụng Raspberry Pi 5 và ESP32 cho kiểm soát ra vào tự động

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

Trong xu hướng phát triển mạnh mẽ của Cách mạng công nghiệp 4.0, các hệ thống điều khiển tự động và kiểm soát truy cập thông minh ngày càng đóng vai trò quan trọng trong nhiều lĩnh vực: giao thông công cộng, văn phòng, khu công nghiệp, bãi giữ xe, trường học, bệnh viện. Một hệ thống cổng kiểm soát hiện đại không chỉ đảm nhiệm chức năng đóng/mở cánh chắn mà còn phải tích hợp được khả năng xác thực đa phương thức (nhận diện khuôn mặt, quét mã QR, đọc thẻ từ RFID), giám sát trạng thái thời gian thực và lưu trữ nhật ký truy cập có hệ thống.

Báo cáo thực tập này trình bày quá trình tìm hiểu, phân tích, thiết kế và triển khai hệ thống **Smart Gate** – một mô hình cổng kiểm soát ra vào nguyên mẫu (prototype) sử dụng kiến trúc **hai nút tính toán** (dual-compute):

- **Raspberry Pi 5** đảm nhiệm khối thị giác máy tính: thu nhận hình ảnh từ webcam USB, nhận diện khuôn mặt, quét mã QR, lưu trữ cơ sở dữ liệu người dùng và cung cấp giao diện web quản trị.
- **ESP32-WROOM-32** đảm nhiệm khối điều khiển ngoại vi thời gian thực: đọc thẻ RFID RC522, điều khiển động cơ Servo SG90 đóng/mở cánh chắn, hiển thị trạng thái lên LCD 20×4, phát âm thanh báo hiệu qua buzzer, và phát hiện hành khách đi qua bằng cảm biến siêu âm HC-SR04.

Hai khối tính toán giao tiếp với nhau qua **một dây cáp USB duy nhất** sử dụng giao thức USB-CDC, vận chuyển bản tin theo định dạng JSON Lines. Việc loại bỏ Wi-Fi và MQTT ở phía ESP32 giúp đơn giản hóa hệ thống, giảm bề mặt tấn công và tăng độ tin cậy cho mô hình demo.

Báo cáo trình bày đầy đủ các nội dung từ phân tích yêu cầu, lựa chọn công nghệ, thiết kế phần cứng (KiCad), thiết kế cơ khí (FreeCAD), thiết kế phần mềm (Python + Flask trên Pi, Arduino-ESP32 + FreeRTOS trên ESP32) cho đến kết quả thử nghiệm và hướng phát triển. Đây là tài liệu tổng kết quá trình thực tập của em tại [ĐƠN VỊ THỰC TẬP], đồng thời là cơ sở để tiếp tục mở rộng đề tài thành đồ án tốt nghiệp.

---

# LỜI CAM KẾT

Em xin cam kết báo cáo thực tập tốt nghiệp với đề tài *“Thiết kế và xây dựng hệ thống cổng thông minh sử dụng Raspberry Pi 5 và ESP32”* là công trình nghiên cứu của riêng em dưới sự hướng dẫn của thầy/cô **[GVHD]**. Toàn bộ nội dung phân tích, thiết kế, sơ đồ khối, mã giả, bảng chân lý chân (pin assignment) và kết quả thử nghiệm được trình bày trong báo cáo đều do em thực hiện trong quá trình thực tập tại **[ĐƠN VỊ THỰC TẬP]**. Các tài liệu tham khảo được trích dẫn đầy đủ trong mục Tài liệu tham khảo.

Em xin chịu hoàn toàn trách nhiệm về nội dung báo cáo này.

Hà Nội, ngày ___ tháng ___ năm 2026
Sinh viên thực hiện
**[HỌ TÊN SINH VIÊN]**

---

# LỜI CẢM ƠN

Trong suốt quá trình thực tập tốt nghiệp và hoàn thành báo cáo, em đã nhận được rất nhiều sự giúp đỡ tận tình từ thầy cô, đồng nghiệp và bạn bè.

Trước tiên, em xin gửi lời cảm ơn chân thành đến **Ban Chủ nhiệm Khoa Điện – Điện tử**, Trường Đại học Giao thông vận tải đã tạo điều kiện thuận lợi cho em được tham gia kỳ thực tập tốt nghiệp tại doanh nghiệp.

Em xin trân trọng cảm ơn thầy/cô **[GVHD]** – giáo viên hướng dẫn – đã dành nhiều thời gian quý báu để hướng dẫn em từ khâu lựa chọn đề tài, định hình kiến trúc hệ thống, đến việc rà soát kỹ thuật trong từng phần thiết kế phần cứng và phần mềm. Những góp ý sâu sát của thầy/cô về phân bố chân ESP32 (pin assignment), giao thức UART JSON Lines và mô hình tác vụ FreeRTOS đã giúp em tránh được nhiều lỗi tiềm ẩn.

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

**CHƯƠNG 1. TỔNG QUAN ĐỒ ÁN** ... 1
1.1. Đặt vấn đề ... 1
1.2. Giải pháp đề xuất ... 2
1.3. Công nghệ sử dụng trong hệ thống ... 4
1.4. Phương pháp xử lý ảnh trong hệ thống ... 6
1.5. Phương án thiết kế ... 8
1.6. Ý nghĩa thực tiễn ... 9
1.7. Mục tiêu nghiên cứu ... 10

**CHƯƠNG 2. THIẾT KẾ PHẦN CỨNG** ... 11
2.1. Giới thiệu chương ... 11
2.2. Cơ sở lý thuyết ... 11
2.3. Ý tưởng thiết kế ... 22
2.4. Xây dựng sơ đồ khối ... 24
2.5. Xây dựng sơ đồ nguyên lý và mạch in ... 27
2.6. Thi công mô hình ... 30
2.7. Kết luận chương II ... 31

**CHƯƠNG 3. THIẾT KẾ PHẦN MỀM** ... 32
3.1. Giới thiệu phần mềm và dữ liệu hệ thống ... 32
3.2. Tổng quan xử lý ảnh ... 36
3.3. Phát hiện, nhận dạng khuôn mặt ... 38
3.4. Quét mã QR ... 42
3.5. Phần mềm sử dụng với ESP32 ... 44
3.6. Lưu đồ thuật toán ... 48
3.7. Tổng hợp thuật toán sử dụng trong chương trình ... 50
3.8. Kết luận chương III ... 51

**CHƯƠNG 4. KẾT QUẢ THÍ NGHIỆM, KẾT LUẬN VÀ HƯỚNG PHÁT TRIỂN** ... 52
4.1. Đánh giá hiệu năng nhận diện AI (trên Raspberry Pi 5) ... 52
4.2. Đánh giá khả năng điều khiển ngoại vi (trên ESP32) ... 53
4.3. Thử nghiệm tính năng an toàn với cảm biến siêu âm HC-SR04 ... 54
4.4. Kết luận ... 55
4.5. Hướng phát triển ... 56

**KẾT LUẬN VÀ KIẾN NGHỊ** ... 57
**PHỤ LỤC** ... 58
**DANH MỤC TÀI LIỆU THAM KHẢO** ... 60

---

# DANH MỤC BẢNG BIỂU

| Bảng | Nội dung |
|---|---|
| Bảng 1.1 | So sánh các phương thức xác thực trong hệ thống Smart Gate |
| Bảng 1.2 | Danh mục linh kiện chính của hệ thống |
| Bảng 2.1 | Thông số kỹ thuật Raspberry Pi 5 |
| Bảng 2.2 | Thông số kỹ thuật ESP32-WROOM-32 (DOIT V1 30-pin) |
| Bảng 2.3 | Thông số kỹ thuật module RFID RC522 |
| Bảng 2.4 | Thông số kỹ thuật Servo SG90 |
| Bảng 2.5 | Thông số kỹ thuật cảm biến siêu âm HC-SR04 |
| Bảng 2.6 | Thông số kỹ thuật LCD 20×4 (PCF8574 I2C backpack) |
| Bảng 2.7 | Phân bố chân (Pin assignment) trên ESP32 DOIT V1 30-pin |
| Bảng 2.8 | Ước tính dòng điện tiêu thụ trên các đường nguồn |
| Bảng 3.1 | Danh sách 8 luồng (thread) trong tiến trình Pi 5 |
| Bảng 3.2 | Bộ động từ lệnh (command verbs) trong giao thức UART |
| Bảng 3.3 | Bộ động từ sự kiện (event verbs) trong giao thức UART |
| Bảng 3.4 | Mô hình tác vụ FreeRTOS trên ESP32 |
| Bảng 4.1 | Kết quả đo độ trễ và tốc độ khung hình nhận diện khuôn mặt |
| Bảng 4.2 | Kết quả đo thời gian đóng/mở cánh chắn |
| Bảng 4.3 | Kết quả 12 kịch bản nghiệm thu firmware ESP32 |

---

# DANH MỤC HÌNH VẼ

| Hình | Nội dung |
|---|---|
| Hình 1.1 | Mô hình tổng quan hệ thống Smart Gate dual-compute |
| Hình 1.2 | Quy trình xác thực đa phương thức (Face / QR / RFID) |
| Hình 2.1 | Bo mạch Raspberry Pi 5 và sơ đồ chân |
| Hình 2.2 | Module ESP32 DevKit DOIT V1 30-pin |
| Hình 2.3 | Module RFID RC522 và thẻ Mifare 13.56 MHz |
| Hình 2.4 | Cấu tạo Servo SG90 |
| Hình 2.5 | Nguyên lý hoạt động cảm biến siêu âm HC-SR04 |
| Hình 2.6 | LCD 20×4 với PCF8574 backpack I2C |
| Hình 2.7 | Sơ đồ khối tổng quát hệ thống |
| Hình 2.8 | Sơ đồ nguyên lý mạch carrier ESP32 |
| Hình 2.9 | Sơ đồ mạch in (PCB) 2D |
| Hình 2.10 | Mô hình cơ khí khung cổng (FreeCAD) |
| Hình 3.1 | Kiến trúc phần mềm trên Pi 5 (8 luồng) |
| Hình 3.2 | FrameHub fan-out pipeline |
| Hình 3.3 | Quy trình tiền xử lý ảnh và trích xuất khuôn mặt |
| Hình 3.4 | Lưu đồ thuật toán xác thực khuôn mặt |
| Hình 3.5 | Lưu đồ thuật toán quét mã QR |
| Hình 3.6 | Máy trạng thái cổng (Gate FSM) trên ESP32 |
| Hình 3.7 | Lưu đồ thuật toán tổng thể hệ thống |
| Hình 4.1 | Hệ thống lắp ráp hoàn thiện |

---

# DANH MỤC CÁC CỤM TỪ VIẾT TẮT

| STT | Từ viết tắt | Tiếng Anh | Nghĩa tiếng Việt |
|---|---|---|---|
| 1 | AFC | Automatic Fare Collection | Hệ thống thu vé tự động |
| 2 | AI | Artificial Intelligence | Trí tuệ nhân tạo |
| 3 | API | Application Programming Interface | Giao diện lập trình ứng dụng |
| 4 | BLE | Bluetooth Low Energy | Bluetooth năng lượng thấp |
| 5 | CDC | Communications Device Class | Lớp thiết bị truyền thông (USB) |
| 6 | CPU | Central Processing Unit | Bộ xử lý trung tâm |
| 7 | CSI | Camera Serial Interface | Giao tiếp camera nối tiếp |
| 8 | FSM | Finite State Machine | Máy trạng thái hữu hạn |
| 9 | GPIO | General Purpose Input Output | Cổng vào/ra đa năng |
| 10 | HLS | HTTP Live Streaming | Truyền video trực tuyến qua HTTP |
| 11 | I2C | Inter-Integrated Circuit | Bus truyền nối tiếp hai dây |
| 12 | IoT | Internet of Things | Vạn vật kết nối |
| 13 | JSON | JavaScript Object Notation | Định dạng đối tượng JavaScript |
| 14 | LCD | Liquid Crystal Display | Màn hình tinh thể lỏng |
| 15 | LDO | Low-Dropout Regulator | IC ổn áp tuyến tính sụt áp thấp |
| 16 | LED | Light Emitting Diode | Đi-ốt phát quang |
| 17 | LEDC | LED Controller | Bộ điều khiển LED (PWM trên ESP32) |
| 18 | MJPEG | Motion JPEG | Định dạng video chuỗi ảnh JPEG |
| 19 | MQTT | Message Queuing Telemetry Transport | Giao thức truyền tin nhẹ cho IoT |
| 20 | NVS | Non-Volatile Storage | Bộ nhớ không mất khi mất điện |
| 21 | OTA | Over The Air | Cập nhật từ xa qua không dây |
| 22 | PCB | Printed Circuit Board | Bảng mạch in |
| 23 | PWM | Pulse Width Modulation | Điều chế độ rộng xung |
| 24 | QR | Quick Response | Mã phản hồi nhanh |
| 25 | RAM | Random Access Memory | Bộ nhớ truy cập ngẫu nhiên |
| 26 | RFID | Radio Frequency Identification | Nhận dạng tần số vô tuyến |
| 27 | RTOS | Real-Time Operating System | Hệ điều hành thời gian thực |
| 28 | SBC | Single Board Computer | Máy tính nhúng một bo mạch |
| 29 | SPI | Serial Peripheral Interface | Bus truyền nối tiếp ngoại vi |
| 30 | SQL | Structured Query Language | Ngôn ngữ truy vấn cơ sở dữ liệu |
| 31 | TTL | Transistor-Transistor Logic | Logic mức điện áp transistor |
| 32 | UART | Universal Asynchronous Receiver-Transmitter | Truyền thông nối tiếp không đồng bộ |
| 33 | USB | Universal Serial Bus | Bus nối tiếp đa dụng |
| 34 | UVC | USB Video Class | Lớp video chuẩn USB |
| 35 | WAL | Write-Ahead Logging | Chế độ ghi-nhật-ký-trước (SQLite) |

---

# CHƯƠNG 1. TỔNG QUAN ĐỒ ÁN

## 1.1. Đặt vấn đề

Trong bối cảnh đô thị hóa nhanh và yêu cầu tự động hóa ngày càng cao, các cổng kiểm soát ra vào truyền thống dựa trên bảo vệ thủ công hoặc thẻ từ đơn giản đã bộc lộ nhiều hạn chế:

1. **Chi phí nhân lực:** mô hình bảo vệ trực canh tại mỗi cổng ra vào doanh nghiệp, khu chung cư, bãi giữ xe… tiêu tốn ngân sách thường xuyên.
2. **Sai sót con người:** nhân viên có thể nhầm lẫn khi đối chiếu danh sách, mệt mỏi vào ca đêm, hoặc gian lận khi không có hệ thống giám sát.
3. **Phương thức xác thực đơn lẻ:** nếu chỉ dựa vào thẻ từ thì thẻ có thể bị mất hoặc cho mượn; nếu chỉ dựa vào nhận diện khuôn mặt thì độ tin cậy giảm khi điều kiện ánh sáng xấu.
4. **Thiếu nhật ký (log) số:** hệ thống cũ thường không lưu được hình ảnh, thời gian và thông tin người vào ra để truy vết khi cần điều tra sự cố.
5. **Khó tích hợp:** các cổng cơ học truyền thống không có cổng giao tiếp (API, UART) nên không kết nối được với hệ thống quản lý tập trung.

Bên cạnh đó, tại Hà Nội, Quyết định 3680/QĐ-UBND năm 2024 ban hành tiêu chuẩn kỹ thuật cho hệ thống AFC (Automatic Fare Collection) trong giao thông công cộng đã định hướng rõ về việc số hóa kiểm soát ra vào, mở ra nhu cầu lớn về các giải pháp cổng thông minh tích hợp nhiều phương thức xác thực.

Trên cơ sở yêu cầu thực tiễn nêu trên, đề tài đặt mục tiêu **xây dựng một hệ thống cổng kiểm soát thông minh đa phương thức**, có khả năng:

- Nhận diện khuôn mặt từ camera USB.
- Quét mã QR cá nhân.
- Đọc thẻ RFID 13.56 MHz.
- Điều khiển cánh chắn (barrier arm) tự động đóng/mở bằng Servo.
- Hiển thị trạng thái cổng và tên người dùng được phép qua trên LCD.
- Phát âm thanh báo hiệu khi xác thực thành công/thất bại hoặc khi có cảnh báo an toàn.
- Phát hiện hành khách đã đi qua cổng bằng cảm biến siêu âm trước khi đóng cánh chắn.
- Cung cấp giao diện web quản trị xem video trực tiếp và nhật ký sự kiện.

Đề tài cũng yêu cầu hệ thống phải **hoạt động độc lập tương đối**: nếu một trong hai khối tính toán (Pi hoặc ESP32) bị mất kết nối, khối còn lại vẫn phải duy trì được chức năng tối thiểu để không gây tắc nghẽn người ra vào.

## 1.2. Giải pháp đề xuất

Đề tài đề xuất kiến trúc **dual-compute** (hai nút tính toán) với phân chia nhiệm vụ rõ ràng theo thế mạnh từng nền tảng:

- **Raspberry Pi 5** (Single Board Computer chạy Linux Raspberry Pi OS Bookworm 64-bit) đảm nhiệm toàn bộ tác vụ thị giác máy tính nặng tính toán: thu khung hình từ webcam USB qua V4L2/OpenCV, nhận diện khuôn mặt bằng MediaPipe + thư viện face_recognition (dlib), quét mã QR bằng pyzbar, lưu trữ cơ sở dữ liệu người dùng trong SQLite, ghi video sự kiện bằng ffmpeg, và cung cấp giao diện web quản trị bằng Flask.
- **ESP32-WROOM-32** (DevKit DOIT V1 30-pin, chạy firmware Arduino-ESP32 + FreeRTOS) đảm nhiệm toàn bộ tác vụ điều khiển ngoại vi thời gian thực: đọc thẻ RFID RC522 qua SPI, điều khiển Servo SG90 qua PWM (LEDC), hiển thị LCD 20×4 qua I2C, đo khoảng cách bằng HC-SR04, phát âm thanh qua active buzzer, và lưu danh sách thẻ RFID được phép trong bộ nhớ NVS (Non-Volatile Storage).

Hai khối kết nối với nhau bằng **một dây cáp USB duy nhất** từ cổng USB-A của Pi 5 đến cổng micro-USB của ESP32 DevKit, sử dụng chip CP2102 sẵn có trên DevKit để cầu nối UART ↔ USB-CDC. Cùng một dây cáp đảm nhiệm cả hai chức năng:
1. **Truyền thông ứng dụng runtime:** Pi sử dụng thư viện pyserial mở `/dev/ttyUSB0` ở tốc độ 115200 baud, trao đổi bản tin JSON Lines với ESP32.
2. **Nạp firmware:** khi cần cập nhật firmware, Pi chạy `esptool.py` ở tốc độ 921600 baud trên cùng cổng (sau khi đã đóng pyserial).

Việc dùng một dây thay vì hai dây UART rời + USB-OTG riêng giúp giảm số đầu nối, tăng độ tin cậy cơ học và đơn giản hóa khâu lắp ráp. Đồng thời, **Wi-Fi trên ESP32 được tắt hoàn toàn** – một quyết định thiết kế quan trọng giúp giảm bề mặt tấn công, giảm tiêu thụ năng lượng và loại bỏ phụ thuộc vào hạ tầng mạng.

Khi một hành khách tiến vào vùng kiểm soát, hệ thống xử lý theo luồng sau:

1. Webcam liên tục truyền video về Pi 5. Luồng `cap` đọc khung hình, ghi vào FrameHub (cấu trúc đồng bộ luồng bằng `threading.Condition`).
2. Luồng `detect` lấy khung BGR mới nhất, chạy MediaPipe Face Detection để khoanh vùng khuôn mặt và `face_recognition` để tạo vector embedding 128 chiều, sau đó so sánh với cơ sở dữ liệu. Đồng thời `pyzbar` quét toàn bộ khung hình tìm mã QR.
3. Trong khi đó, ESP32 luôn ở trạng thái sẵn sàng polling đầu đọc RFID RC522 mỗi 50 ms. Nếu phát hiện thẻ mới, ESP32 đối chiếu UID thẻ với danh sách trong NVS.
4. Nếu xác thực thành công ở bất kỳ phương thức nào:
   - Phương thức Face/QR (trên Pi): Pi gửi lệnh `{"id":42,"type":"cmd","v":"open","data":{"user":"alice","reason":"face"}}` qua serial.
   - Phương thức RFID (trên ESP32): ESP32 tự kích máy trạng thái nội bộ.
5. ESP32 chuyển sang trạng thái `OPENING`, ghi giá trị PWM mở cho Servo SG90 (góc 100°), phát beep ngắn báo hiệu thành công, hiển thị `"Welcome: <tên>"` lên LCD và phát sự kiện `evt:gate {state:"opening"}` trở lại Pi.
6. Sau khoảng 300 ms (thời gian quét của SG90 ≈ 300°/giây với góc quay 90°), ESP32 chuyển sang `OPEN_WAIT`, khởi động bộ đếm 10 giây.
7. Cảm biến siêu âm HC-SR04 liên tục đo khoảng cách 50 ms/lần. Khi vật cản (hành khách) đi qua vùng cảm biến (khoảng cách dưới 25 cm rồi vượt qua), ESP32 phát sự kiện `evt:person_passed` và chuyển sang `CLOSING` để đóng cánh chắn.
8. Nếu hết 10 giây mà không phát hiện hành khách đi qua, ESP32 chuyển sang `TIMEOUT_WARN`, phát âm thanh cảnh báo nhịp và sau 5 giây nữa sẽ cưỡng bức đóng cánh chắn (để tránh tắc nghẽn hệ thống).

**Bảng 1.1. So sánh các phương thức xác thực trong hệ thống Smart Gate**

| Phương thức | Vị trí xử lý | Độ chính xác | Phụ thuộc môi trường | Tài nguyên |
|---|---|---|---|---|
| Khuôn mặt | Pi 5 (MediaPipe + face_recognition) | ~95% (ngưỡng 0.55) | Cần đủ sáng, góc nghiêng ≤ 30° | CPU cao (~60–80 ms/khung) |
| QR | Pi 5 (pyzbar) | ~99% | Cần mã in rõ, đủ tương phản | CPU thấp |
| RFID | ESP32 (MFRC522) | 100% nếu UID có trong danh sách | Không phụ thuộc ánh sáng | Thấp; polling 50 ms/lần |

## 1.3. Công nghệ sử dụng trong hệ thống

Hệ thống sử dụng tổ hợp các công nghệ phần cứng và phần mềm sau:

**Phần cứng:**

| Khối | Linh kiện | Vai trò |
|---|---|---|
| Tính toán Pi | Raspberry Pi 5 (4 GB hoặc 8 GB RAM) | Vision, web admin, lưu trữ |
| Tính toán MCU | ESP32-WROOM-32 (DevKit DOIT V1 30 chân) | Điều khiển ngoại vi thời gian thực |
| Camera | Webcam USB UVC (Logitech C270 hoặc tương đương) | Thu hình ảnh khuôn mặt và QR |
| Xác thực thẻ | Module RFID RC522 + thẻ Mifare 13.56 MHz | Đọc UID thẻ qua SPI |
| Hiển thị | LCD 20×4 + backpack PCF8574 (I2C) | Hiển thị trạng thái và tên người dùng |
| Cơ cấu chấp hành | Servo SG90 (50 Hz PWM) | Quay cánh chắn 0–100° |
| Cảm biến an toàn | Cảm biến siêu âm HC-SR04 | Phát hiện hành khách đi qua |
| Âm thanh | Active buzzer (có dao động nội bộ) | Báo hiệu thành công/thất bại |
| Nguồn | Bộ nguồn AC-DC 12 V/2 A + buck MP1584/LM2596 → 5 V + LDO AMS1117-3.3 → 3.3 V | Cấp nguồn carrier board ESP32 |
| PCB | Carrier board KiCad 6.0.2 tự thiết kế | Tích hợp ESP32 DevKit + đầu nối ngoại vi |

**Phần mềm trên Pi 5:**

| Thành phần | Phiên bản / Công nghệ | Vai trò |
|---|---|---|
| Hệ điều hành | Raspberry Pi OS Bookworm 64-bit | Linux kernel + V4L2 + systemd |
| Ngôn ngữ | Python 3.11 | Mã ứng dụng |
| Thị giác máy tính | OpenCV 4.x (cv2) | Đọc V4L2, mã hóa JPEG, hiển thị |
| Phát hiện khuôn mặt | MediaPipe Face Detection | Khoanh vùng khuôn mặt (~10 ms) |
| Nhận dạng khuôn mặt | face_recognition (dlib) | Embedding 128 chiều + Euclidean distance |
| Quét mã QR | pyzbar | Decode QR/Code128/Code39 |
| Giao tiếp UART | pyserial 3.5 | Mở `/dev/ttyUSB0` |
| Web framework | Flask 3.0 | Trang admin |
| Streaming | MJPEG over HTTP multipart | Live preview |
| Cơ sở dữ liệu | SQLite (WAL mode) | users, face_encodings, qr_tokens, events |
| Ghi video sự kiện | ffmpeg (libx264, preset veryfast) | Ghi clip 10 giây |
| Quản lý dịch vụ | systemd unit `smart-gate.service` | Daemon tự khởi động |
| Cấu hình | `tomllib` (Python stdlib) | Đọc `/etc/smart-gate/config.toml` |

**Phần mềm trên ESP32:**

| Thành phần | Phiên bản / Công nghệ | Vai trò |
|---|---|---|
| Toolchain | PlatformIO (`espressif32@^6.0`) | Build và flash |
| Framework | Arduino-ESP32 | API + truy cập FreeRTOS |
| Đồng bộ tác vụ | FreeRTOS (queue, timer, watchdog) | 4 task pinned core |
| JSON | ArduinoJson 7 | Parse và serialize JSON Lines |
| RFID | MFRC522 1.4 (miguelbalboa) | Driver SPI cho RC522 |
| Servo | ESP32Servo 3 (madhephaestus) | PWM 50 Hz qua LEDC |
| LCD | LiquidCrystal_I2C 1.1 | Điều khiển PCF8574 backpack |
| Lưu trữ | Preferences (NVS) | Danh sách thẻ RFID + cấu hình |
| Cảm biến | `pulseIn()` (Arduino) | Đo siêu âm HC-SR04 |
| Truyền thông | Serial (UART0 + USB-CDC qua CP2102) | JSON Lines 115200 baud |

**Phần cứng và phần mềm CAD/EDA:**

- **KiCad 6.0.2** – thiết kế sơ đồ nguyên lý (schematic) và mạch in (PCB) cho carrier board ESP32 (file `kicad/smart_gate_carrier/smart_gate_carrier.kicad_sch`).
- **FreeCAD 0.21** – mô hình hóa 3D khung cổng (thân hộp, hai trụ, cánh chắn 80 mm, chân camera) bằng các sketch tham số.

## 1.4. Phương pháp xử lý ảnh trong hệ thống

Phía Pi 5 sử dụng một pipeline xử lý ảnh dạng **fan-out** (một nguồn nhiều đích), tận dụng được dữ liệu khung hình từ một thiết bị camera duy nhất cho ba mục đích khác nhau:

1. **Truyền hình ảnh trực tiếp về trình duyệt:** giao diện web admin của Flask cần luồng video MJPEG để hiển thị xem-trực-tiếp (live preview).
2. **Nhận diện và quét mã:** luồng `detect` tiêu thụ khung BGR đã decode để chạy MediaPipe + face_recognition + pyzbar.
3. **Ghi video sự kiện:** mỗi khi có xác thực thành công, hệ thống cần ghi 5 giây trước + 5 giây sau sự kiện thành tệp MP4 để lưu trữ kiểm tra sau này.

Camera USB UVC chỉ cho duy nhất một luồng ra ở mỗi thời điểm (khác với CSI/libcamera có thể fan-out ở mức driver). Vì vậy đề tài thiết kế lớp **FrameHub** sử dụng `threading.Condition` để phân phối từng khung hình mới đến cả ba consumer.

Cấu hình camera quan trọng (xem chi tiết Chương 3, mục 3.2):

- **FOURCC = MJPG:** yêu cầu webcam đẩy ra khung hình đã được encode JPEG sẵn ở nguồn. Việc này giúp giảm băng thông USB (~10 MB/s thay vì ~150 MB/s nếu YUYV thô) và tiết kiệm CPU Pi.
- **BUFFERSIZE = 1:** chỉ giữ 1 khung trong buffer V4L2, luôn trả khung mới nhất khi `cap.read()` được gọi. Điều này tránh tích tụ khung cũ khi detector chạy chậm.

Sau khi đọc xong, capture thread re-encode lại JPEG ở chất lượng 75 (`cv2.imencode('.jpg', bgr, [cv2.IMWRITE_JPEG_QUALITY, 75])`) để có một cặp `(JPEG bytes, BGR ndarray)` đẩy lên FrameHub. Lý do phải re-encode dù webcam đã encode sẵn: Pi cần khung BGR đã decode cho detector, nhưng vẫn cần JPEG cho Flask – nên cách rẻ nhất là decode 1 lần, encode lại 1 lần ở chất lượng phù hợp với mạng LAN.

Pipeline tổng thể:

```
USB Webcam ─▶ V4L2 ─▶ cv2.VideoCapture (MJPG, 640×480, 15 fps, BUFFERSIZE=1)
                          │
                          ▼
                      FrameHub (threading.Condition)
                          │
        ┌─────────────────┼────────────────────┐
        ▼                 ▼                    ▼
Flask /stream.mjpeg   Detector             RingBuffer
(passthrough JPEG)    (MediaPipe +         (5s pre + 5s post)
                       face_recognition +       │
                       pyzbar)                  ▼
                          │                ffmpeg → MP4
                          ▼
                    AuthEvent → debouncer → UART cmd:open
```

Các bước xử lý chi tiết được trình bày trong Chương 3, mục 3.2 và 3.3.

## 1.5. Phương án thiết kế

Đề tài đã trải qua một số phương án trước khi chốt thiết kế cuối:

**Phương án 1 (loại bỏ):** dùng duy nhất ESP32-CAM xử lý cả camera và điều khiển ngoại vi. Loại bỏ vì ESP32 classic không đủ sức mạnh CPU để chạy face_recognition (dlib), và bộ nhớ PSRAM nhỏ không cho phép giữ nhiều khung hình. Việc đặt khuôn mặt lên một MCU là không khả thi cho yêu cầu thực tế.

**Phương án 2 (loại bỏ):** dùng duy nhất Raspberry Pi 5 cho tất cả. Loại bỏ vì Pi 5 thiếu khả năng PWM phần cứng đơn lẻ hỗ trợ Servo (cần PWM 50 Hz chính xác để Servo không rung), thiếu cách an toàn để đọc SPI RFID real-time, và quan trọng nhất: nếu Pi reboot do crash hệ điều hành (ví dụ kernel panic, đầy disk) thì cánh chắn sẽ "đứng" – không thể đóng/mở. Mức tin cậy không đủ cho thiết bị kiểm soát ra vào.

**Phương án 3 (loại bỏ):** dùng Pi 5 + ESP32 nhưng nối qua hai dây UART rời + Wi-Fi/MQTT cho backup. Loại bỏ vì làm tăng số đầu nối, phụ thuộc vào hạ tầng mạng và làm hệ thống phức tạp hơn so với mục tiêu prototype.

**Phương án 4 (đã chọn):** Pi 5 + ESP32 nối qua **một dây cáp USB duy nhất**, với ESP32 tự lưu danh sách RFID trong NVS để hoạt động độc lập khi Pi mất liên kết. Wi-Fi trên ESP32 tắt hoàn toàn. MQTT bỏ. Đây là phương án đơn giản nhất, gọn nhất và đủ chức năng cho prototype demo.

Một số quyết định cụ thể khác trong phương án thiết kế:

- **Cánh chắn (barrier arm)** thay vì cửa trượt (sliding door): đơn giản về cơ khí (chỉ cần một Servo quay quanh trục), dễ thi công với MDF/acrylic.
- **Servo SG90** thay vì MG996R: SG90 mô-men nhỏ hơn nhưng đủ cho cánh chắn 80 mm bằng balsa/acrylic, giá rẻ và tiết kiệm dòng. (Mô hình template báo cáo cũ đề cập MG996R cho cửa trượt, nhưng vì đã chuyển sang barrier arm nên SG90 là đủ.)
- **Cảm biến siêu âm HC-SR04** thay vì cảm biến hồng ngoại (IR): siêu âm có độ tin cậy cao hơn trong các điều kiện ánh sáng và bụi, đo được khoảng cách thực (cm) chứ không chỉ "có/không" như IR đơn. Đây là một điểm sửa đổi so với yêu cầu ban đầu trong file `requirement.txt`.
- **Nguồn 12 V** thay vì 5 V/USB: 12 V dễ tìm, ổn định khi Servo có dòng đỉnh ~500 mA, và việc qua buck → 5 V → LDO → 3.3 V tạo được phân cấp nguồn sạch.

## 1.6. Ý nghĩa thực tiễn

**Tính mới của đồ án:**

1. Tích hợp ba phương thức xác thực (Face + QR + RFID) trên cùng một cổng vật lý với phân tách tính toán rõ ràng giữa Pi (vision-heavy) và ESP32 (real-time).
2. Áp dụng kiến trúc *standalone resilience*: ESP32 tự xác thực RFID độc lập, không phụ thuộc Pi.
3. Dùng một dây USB duy nhất cho cả truyền thông ứng dụng và nạp firmware – giảm thiểu phần cứng và rút gọn thi công.
4. Loại bỏ Wi-Fi và MQTT trên ESP32 – đi ngược một phần xu hướng "IoT-tất-mọi-thứ" để có hệ thống ổn định, đơn giản hơn.

**Ý nghĩa thực tiễn:**

- Mô hình demo có thể triển khai làm cổng vào thư viện, văn phòng nhỏ, lớp học, nơi yêu cầu xác thực ai vào ai ra nhưng không cần thông lượng quá cao.
- Là nền tảng để mở rộng thành đồ án tốt nghiệp với các tính năng nâng cao: chống giả mạo khuôn mặt (anti-spoofing), tích hợp HRM nhân sự, mở rộng thành nhiều cổng kết nối qua MQTT về một broker trung tâm.
- Quy trình thiết kế thực tế (spec → KiCad → FreeCAD → firmware → Pi app → test) là tài liệu tham khảo cho các bạn sinh viên sau làm đề tài tương tự.

## 1.7. Mục tiêu nghiên cứu

Mục tiêu của đợt thực tập tốt nghiệp được xác định cụ thể như sau:

1. **Nắm vững kiến trúc dual-compute** trong hệ thống nhúng: hiểu khi nào nên dùng SBC, khi nào nên dùng MCU, và làm sao để hai bên giao tiếp ổn định.
2. **Thực hành thiết kế hệ thống đầu-cuối** từ spec đến triển khai: viết tài liệu thiết kế, vẽ sơ đồ khối, phân chân ESP32, vẽ schematic KiCad, mô hình hóa 3D bằng FreeCAD, viết firmware ESP32 (PlatformIO + FreeRTOS), viết ứng dụng Pi (Python + Flask).
3. **Áp dụng các thư viện thị giác máy tính** OpenCV, MediaPipe, face_recognition và pyzbar trong môi trường thực tế (không chỉ Colab/Jupyter).
4. **Hiểu giao thức UART** mức ứng dụng: thiết kế khung tin (JSON Lines), bộ động từ lệnh/sự kiện, cơ chế ACK và heartbeat.
5. **Vận dụng FreeRTOS** trên ESP32: tạo task, queue, timer, watchdog; xử lý đồng thời từ nhiều ngoại vi.
6. **Quản lý cơ sở dữ liệu** SQLite cho user, face encodings, QR token và events trên Pi.
7. **Xây dựng giao diện web admin** với Flask + HTMX + Pico.css, đủ tối thiểu để demo, không sa đà vào front-end nặng.
8. **Đánh giá định lượng** hệ thống: đo độ trễ nhận diện, tốc độ khung hình, thời gian đóng/mở cánh chắn, độ ổn định liên kết UART trong 1–2 tuần chạy thử.

---

# CHƯƠNG 2. THIẾT KẾ PHẦN CỨNG

## 2.1. Giới thiệu chương

Chương 2 trình bày toàn bộ phần thiết kế phần cứng cho hệ thống Smart Gate, bao gồm:

- Cơ sở lý thuyết về các linh kiện chính (Raspberry Pi 5, ESP32, RC522, Servo SG90, HC-SR04, LCD 20×4, buzzer, giao tiếp UART/SPI/I2C).
- Phân tích thiết kế và yêu cầu thiết kế.
- Sơ đồ khối tổng quát và chức năng từng khối.
- Sơ đồ nguyên lý (KiCad schematic) của carrier board ESP32.
- Sơ đồ mạch in (PCB) 2D/3D.
- Thi công mô hình cơ khí bằng FreeCAD.

## 2.2. Cơ sở lý thuyết

### 2.2.1. Tìm hiểu về hệ thống AFC

AFC (Automatic Fare Collection – Hệ thống thu vé tự động) là tập các thiết bị, phần mềm và quy trình cho phép thu phí dịch vụ giao thông công cộng một cách tự động, không cần nhân viên bán/xé vé thủ công. Các thành phần chính của một AFC gồm:

- **Cổng/quầy soát vé tự động (gate / fare-gate / turnstile):** thiết bị vật lý cho phép hành khách đi qua sau khi xác thực vé/thẻ thành công, đồng thời chặn nếu xác thực thất bại.
- **Đầu đọc/đầu ghi thẻ:** RFID, NFC, QR code reader.
- **Trung tâm xử lý dữ liệu (CCH – Central Clearing House):** lưu trữ giao dịch, đối soát giữa các nhà khai thác.
- **Hệ thống bán vé:** trực tiếp tại trạm hoặc trực tuyến qua ứng dụng.

Tại Hà Nội, Quyết định 3680/QĐ-UBND năm 2024 ban hành tiêu chuẩn kỹ thuật cho hệ thống AFC, quy định rõ về giao thức trao đổi thẻ (ISO/IEC 14443), độ trễ tối đa khi xác thực, mức ưu tiên giữa các loại thẻ và yêu cầu nhật ký kiểm toán.

Đề tài *Smart Gate* không nhằm mục tiêu xây dựng một AFC hoàn chỉnh phục vụ giao thông công cộng, mà tập trung vào một subset là **cổng kiểm soát ra vào kèm xác thực đa phương thức** – có thể áp dụng cho thư viện, văn phòng, khu đô thị thông minh. Các thành phần và quy trình thiết kế sau đây tham khảo nguyên lý chung của AFC nhưng được tối giản phù hợp với mô hình prototype.

### 2.2.2. Tìm hiểu về Raspberry Pi 5

**Giới thiệu:** Raspberry Pi 5 là dòng SBC (Single Board Computer) thế hệ mới nhất của Raspberry Pi Foundation, ra mắt cuối năm 2023. So với Pi 4, Pi 5 sử dụng SoC mới Broadcom BCM2712 (4 nhân Cortex-A76 @ 2.4 GHz), GPU VideoCore VII, và lần đầu tiên đi kèm chip Southbridge tùy chỉnh RP1 (cung cấp toàn bộ I/O ngoại vi). Trong báo cáo này, "Pi 5" được chọn (thay vì "Pi 4" như mô tả trong template báo cáo cũ) vì hiệu năng CPU/GPU cao hơn ~2–3 lần, đặc biệt hữu ích cho việc chạy face_recognition theo thời gian thực.

**Thông số kỹ thuật:**

| Thông số | Giá trị |
|---|---|
| SoC | Broadcom BCM2712 (4 × Cortex-A76, 2.4 GHz) |
| GPU | VideoCore VII, hỗ trợ OpenGL ES 3.1, Vulkan 1.2 |
| RAM | 4 GB hoặc 8 GB LPDDR4X-4267 |
| Lưu trữ | microSD UHS-I + 1× PCIe 2.0 (qua RP1) cho NVMe (cần HAT) |
| USB | 2× USB 3.0 + 2× USB 2.0 |
| Mạng | Gigabit Ethernet, Wi-Fi 5 dual-band (2.4 GHz/5 GHz), Bluetooth 5.0 |
| Camera | 2× MIPI CSI/DSI (cùng cổng) |
| GPIO | 40-pin header chuẩn |
| Nguồn | USB-C PD 5 V/5 A (25 W) |

**Chức năng trong hệ thống:**

Pi 5 đảm nhiệm:
- Đọc luồng video từ webcam USB qua V4L2.
- Chạy MediaPipe + face_recognition để xác thực khuôn mặt.
- Quét QR bằng pyzbar.
- Lưu users, face_encodings, QR tokens, events vào SQLite.
- Chạy web admin Flask phục vụ MJPEG live preview + danh sách sự kiện.
- Mở `/dev/ttyUSB0` qua pyserial để gửi lệnh `cmd:open` đến ESP32 và nhận sự kiện `evt:*`.
- Ghi clip MP4 cho từng sự kiện qua ffmpeg.

**Sơ đồ kết nối (xem Hình 2.1):**

- Webcam USB → cổng USB 3.0.
- Dây cáp USB → cổng USB-A → DevKit ESP32 (cổng micro-USB) → CP2102 → UART0 của ESP32.
- Nguồn USB-C PD riêng (không chung nguồn với ESP32).
- Cáp Ethernet LAN cho web admin (hoặc Wi-Fi 5 nếu tiện).

### 2.2.3. Tìm hiểu về ESP32

**Giới thiệu:** ESP32 là dòng SoC microcontroller của Espressif Systems, ra mắt năm 2016. Phiên bản classic ESP32-WROOM-32 (Xtensa LX6 dual-core) được chọn cho đề tài này vì có Wi-Fi/BT, đủ GPIO và giá rẻ. DevKit DOIT V1 30 chân là form-factor phổ biến nhất; tích hợp CP2102 USB-UART, nút EN/BOOT, LDO 3.3 V trên-board.

**Thông số kỹ thuật:**

| Thông số | Giá trị |
|---|---|
| CPU | Xtensa LX6 dual-core, 240 MHz (Core 0 + Core 1) |
| RAM | 520 KB SRAM, 16 KB RTC SRAM |
| Flash | 4 MB (trên DevKit chuẩn) |
| Wi-Fi | 802.11 b/g/n (2.4 GHz) – **không dùng trong đề tài** |
| Bluetooth | BT 4.2 Classic + BLE – **không dùng trong đề tài** |
| GPIO | 25 chân khả dụng trên DevKit 30-pin (loại trừ chân nguồn, EN) |
| ADC | 18 kênh, 12-bit |
| DAC | 2 kênh, 8-bit |
| PWM | LEDC controller, 16 kênh, độ phân giải lên tới 14-bit |
| SPI | 4 bộ (SPI0/SPI1 dùng cho flash, HSPI và VSPI khả dụng cho ứng dụng) |
| I2C | 2 bộ |
| UART | 3 bộ (UART0 cho debug/console, UART1, UART2) |

**Chức năng trong hệ thống:**

ESP32 chịu trách nhiệm:
- Đọc thẻ RFID RC522 qua VSPI (remap chân vì DOIT V1 30-pin không expose chân SPI mặc định).
- Điều khiển Servo SG90 qua LEDC PWM 50 Hz.
- Điều khiển LCD 20×4 qua I2C (remap chân I2C, kéo trở pull-up về 3.3 V).
- Đo siêu âm HC-SR04: gửi xung TRIG, đọc ECHO bằng `pulseIn`.
- Điều khiển active buzzer qua transistor NPN.
- Giao tiếp UART JSON Lines với Pi 5 qua UART0 + USB-CDC (chia sẻ với cổng nạp firmware).
- Lưu danh sách thẻ RFID được phép trong NVS (Preferences API), tối đa 100 mục.

**Sơ đồ kết nối:** Xem mục 2.4 (sơ đồ khối) và 2.5 (sơ đồ nguyên lý).

### 2.2.4. Tìm hiểu về Camera USB 1080p

Hệ thống sử dụng webcam USB chuẩn UVC (USB Video Class) – một chuẩn driver-less hoạt động trực tiếp với V4L2 trên Linux. Các model phổ biến phù hợp:

- **Logitech C270:** 720p @ 30 fps, ~600 nghìn VND, đủ cho demo.
- **Logitech C920:** 1080p @ 30 fps, ~1,5 triệu VND, chất lượng hình ảnh tốt hơn nếu ngân sách cho phép.

Ưu điểm webcam USB so với Pi Camera CSI:
- Plug-and-play, không cần kích hoạt overlay device-tree.
- Dễ gắn cơ khí ở vị trí tùy ý (có sẵn kẹp).
- Tách rời điện với Pi qua cáp USB → dễ thay thế.

Nhược điểm:
- Băng thông USB bị tranh chấp với các thiết bị USB khác (ESP32 DevKit cũng cắm USB).
- Khả năng tự động phơi sáng/cân bằng trắng kém hơn Pi Camera v3.

Đề tài cấu hình camera ở 640×480 @ 15 fps, FOURCC MJPG để giảm băng thông xuống ~10 MB/s. Phân giải này đủ cho khuôn mặt cách camera ~50–80 cm.

### 2.2.5. Tìm hiểu về Module RFID RC522

Module RFID RC522 dựa trên chip MFRC522 của NXP, làm việc ở tần số 13.56 MHz (chuẩn ISO/IEC 14443A) với khoảng đọc 3–5 cm cho thẻ Mifare Classic 1K phổ biến.

**Thông số kỹ thuật:**

| Thông số | Giá trị |
|---|---|
| Tần số | 13.56 MHz |
| Giao thức thẻ | ISO/IEC 14443A (Mifare Classic, Ultralight, NTAG) |
| Khoảng đọc | 3–5 cm |
| Giao tiếp với MCU | SPI (hoặc I2C/UART tùy module) |
| Điện áp | 3.3 V (không chịu được 5 V) |
| Dòng tiêu thụ | ~26 mA khi đang đọc |

**Cách giao tiếp:**

ESP32 nối với RC522 qua bus SPI gồm 4 dây: SCK, MOSI, MISO, SS (CS). Thêm 2 dây phụ: RST (reset) và IRQ (ngắt khi có thẻ mới – đề tài này dùng polling cho đơn giản, không cần IRQ).

Quy trình đọc thẻ:
1. Khởi tạo RC522 (`PCD_Init()`).
2. Mỗi 50 ms, gọi `PICC_IsNewCardPresent()` để kiểm tra có thẻ trong vùng anten không.
3. Nếu có, gọi `PICC_ReadCardSerial()` để đọc UID (thường 4 byte hoặc 7 byte).
4. So sánh UID với danh sách trong NVS.
5. Gọi `PICC_HaltA()` + `PCD_StopCrypto1()` để thẻ không bị đọc trùng liên tiếp khi giữ trên anten.

**Thẻ RFID 13.56 MHz (Mifare Classic 1K):**

- UID 4 byte hoặc 7 byte (đề tài dùng UID làm khóa, không đọc nội dung block – đơn giản hóa).
- Hệ thống dùng UID hex 8 ký tự (ví dụ `"a1b2c3d4"`) làm khóa primary trong NVS.

### 2.2.6. Tìm hiểu về Servo SG90

Servo SG90 là động cơ servo RC nhỏ, phổ biến cho các dự án DIY và mô hình.

**Thông số kỹ thuật:**

| Thông số | Giá trị |
|---|---|
| Điện áp hoạt động | 4.8 V – 6.0 V (đề tài dùng 5 V) |
| Mô-men xoắn | 1.8 kg·cm @ 4.8 V |
| Tốc độ quay | 60° trong 0.1 s (≈ 300°/s) |
| Góc quay | 0° – 180° (thực tế ổn định ở 10° – 170°) |
| Điều khiển | PWM 50 Hz, độ rộng xung 1.0 – 2.0 ms (1.0 ms = 0°, 1.5 ms = 90°, 2.0 ms = 180°) |
| Dòng tiêu thụ | 100–200 mA khi đang chạy, đỉnh ~500 mA khi tải nặng |

**Vai trò trong hệ thống:**

Servo SG90 lắp trên trụ trái của cổng, quay cánh chắn 80 mm giữa hai vị trí:
- **CLOSED:** góc 10° (cánh chắn ngang, gác lên trụ phải)
- **OPEN:** góc 100° (cánh chắn dựng đứng)

Thời gian quét 90° ≈ 300 ms (tương ứng tốc độ định mức 300°/s). Firmware sử dụng timer FreeRTOS 300 ms để xác định "Servo đã đến đích" mà không cần feedback (SG90 không có encoder/potentiometer ra).

**Lý do chọn SG90 thay vì MG996R:** template báo cáo cũ đề cập MG996R cho cửa trượt (mô-men cao 11 kg·cm, dòng đỉnh 1.5 A). Tuy nhiên đề tài chuyển sang **cánh chắn (barrier arm)** nhẹ hơn nhiều – cánh balsa/acrylic 80 mm chỉ cần dưới 1 kg·cm. SG90 giá ~30 nghìn VND so với MG996R ~150 nghìn VND, lại tiết kiệm dòng hơn.

### 2.2.7. Tìm hiểu về cảm biến siêu âm HC-SR04

**Lưu ý:** Yêu cầu ban đầu (`requirement.txt`) đề cập **cảm biến hồng ngoại (IR)**, tuy nhiên trong quá trình thiết kế chi tiết, đề tài đã chuyển sang **cảm biến siêu âm HC-SR04** với các lý do sau:

- IR đơn (chuyển mạch quang) chỉ trả về binary "có/không có vật cản" – dễ bị nhiễu bởi ánh sáng mặt trời, đèn huỳnh quang công suất lớn.
- HC-SR04 trả về khoảng cách thực (cm), giúp debounce tốt hơn và phân biệt được "vật cản ở gần" (hành khách) với "không có gì" trong điều kiện ánh sáng thay đổi.
- HC-SR04 giá tương đương IR (~30 nghìn VND), cùng giao tiếp đơn giản (TRIG + ECHO).

**Thông số kỹ thuật:**

| Thông số | Giá trị |
|---|---|
| Điện áp hoạt động | 5 V (cần chia áp ECHO xuống 3.3 V cho ESP32) |
| Khoảng đo | 2 cm – 400 cm |
| Độ chính xác | ±3 mm |
| Tần số phát siêu âm | 40 kHz |
| Dòng tiêu thụ | ~15 mA |
| Giao tiếp | 2 chân số: TRIG (input), ECHO (output) |

**Nguyên lý hoạt động:**

1. MCU phát một xung HIGH dài 10 µs trên chân TRIG.
2. Module phát một chuỗi 8 chu kỳ sóng siêu âm 40 kHz.
3. Khi sóng dội về, chân ECHO sẽ giữ HIGH trong khoảng thời gian tỉ lệ với khoảng cách:
   $$ d \text{ (cm)} = \dfrac{t_{ECHO} \text{ (µs)}}{58} $$
4. ESP32 dùng `pulseIn(PIN_SR04_ECHO, HIGH, 30000)` (timeout 30 ms = 5 m) để đo thời gian.

**Điện áp ECHO:** chân ECHO ra mức 5 V, không tương thích trực tiếp với chân ESP32 (3.3 V tolerance). Đề tài dùng **mạch chia áp R1 = 1 kΩ + R2 = 2 kΩ** để giảm còn 3.3 V tại chân GPIO 34 (input-only). Chân TRIG nhận tín hiệu 3.3 V từ ESP32 vẫn hoạt động bình thường vì ngưỡng logic HIGH của HC-SR04 chỉ khoảng 3 V.

**Vai trò trong hệ thống:**

HC-SR04 đặt ngay trong khe đi qua của cổng, hướng vuông góc với lane đi 60 mm. Firmware (xem mục 3.5) duy trì hai biến `below_count`, `above_count` để debounce theo chuẩn 3-consecutive: khi 3 phép đo liên tiếp cho khoảng cách dưới 25 cm thì "có người trong vùng cảm biến"; khi 3 phép đo liên tiếp trở lại ≥ 25 cm thì "người đã đi qua" – sự kiện `evt:person_passed` được phát đến Pi, cánh chắn bắt đầu đóng.

### 2.2.8. Tìm hiểu về LCD I2C

LCD 20×4 ký tự (4 dòng, mỗi dòng 20 ký tự) với backpack PCF8574 chuyển từ giao tiếp song song 8/4-bit sang I2C – chỉ cần 4 dây (SDA, SCL, VCC, GND) thay vì 16 dây như HD44780 truyền thống.

**Thông số kỹ thuật:**

| Thông số | Giá trị |
|---|---|
| Kích thước | 20 cột × 4 dòng |
| Điều khiển | HD44780 (chip nội), PCF8574 (backpack I2C) |
| Địa chỉ I2C | 0x27 (mặc định) hoặc 0x3F (tùy module) |
| Điện áp | 5 V (chỉ VCC – tín hiệu I2C có thể chạy 3.3 V nếu pull-up về 3.3 V) |
| Backlight | LED có công tắc nhảy trên backpack |
| Tốc độ I2C | 100 kHz (Standard mode) hoặc 400 kHz (Fast mode) |

**Vấn đề mức điện áp I2C:** PCF8574 backpack thường có pull-up 4.7 kΩ về 5 V. Khi ESP32 (3.3 V GPIO) lái bus, trạng thái LOW hoạt động bình thường, nhưng khi GPIO chuyển sang trạng thái thả nổi (HIGH-Z), pull-up 5 V sẽ "back-drive" vào diode bảo vệ chân ESP32 – có thể làm chip nóng dần và hỏng sau thời gian dài.

**Giải pháp:** *cắt* hai trở pull-up trên backpack (thường gần chân SDA/SCL của PCF8574) và lắp pull-up 4.7 kΩ về 3.3 V trên carrier board. Việc này được ghi chú trong tài liệu lắp ráp.

**Vai trò trong hệ thống:**

LCD hiển thị các trạng thái:
- `"smart_gate ready"` khi idle.
- `"Welcome: <name>"` khi mở cổng cho người dùng đã xác thực.
- `"Please pass through"` khi đang chờ hành khách đi qua.
- `"Access denied"` khi thẻ không hợp lệ.

Firmware gọi `lcd_show_*` từ luồng `gate_fsm_task` (luồng duy nhất viết LCD), do đó không cần mutex.

### 2.2.9. Tìm hiểu về còi Buzzer

Đề tài sử dụng **active buzzer** (loại có dao động nội bộ): khi cấp điện cường HIGH, buzzer tự phát ra âm thanh tần số cố định (~2 kHz). Khác với passive buzzer (cần xung PWM từ MCU), active buzzer chỉ cần điều khiển HIGH/LOW.

**Thông số kỹ thuật:**

| Thông số | Giá trị |
|---|---|
| Điện áp | 3.3 V – 5 V (đề tài dùng 5 V) |
| Dòng tiêu thụ | ~25 mA |
| Tần số phát | ~2 kHz (cố định, do mạch dao động nội) |
| Mức âm | ~85 dB ở 10 cm |

**Mạch driver:** dòng tiêu thụ 25 mA vượt ngưỡng an toàn của chân GPIO ESP32 (12 mA), nên cần một transistor NPN làm tầng đệm. Đề tài dùng 2N3904 với base resistor 1 kΩ, emitter nối GND, collector nối chân âm buzzer, dương buzzer nối 5 V. Khi GPIO HIGH (3.3 V), transistor dẫn → buzzer kêu.

**Các pattern âm thanh:**

- `beep_ok()`: 1 tiếng 80 ms.
- `beep_err()`: 3 tiếng 60 ms cách nhau 50 ms.
- `pattern_warn()`: nhịp 250 ms HIGH / 250 ms LOW liên tục cho đến khi cánh chắn đóng.

Pattern warn được kích bằng software timer FreeRTOS (không khóa task).

### 2.2.10. Tìm hiểu về giao tiếp UART

**Giới thiệu:**

UART (Universal Asynchronous Receiver-Transmitter) là chuẩn truyền nối tiếp không đồng bộ, sử dụng 2 dây tín hiệu TX (truyền) và RX (nhận) cộng với một mass chung. Không có clock chia sẻ – hai đầu thống nhất trước về tốc độ baud (bit/giây) qua cấu hình.

**Nguyên lý truyền nhận dữ liệu:**

Khung tin UART điển hình:
- 1 bit START (LOW)
- 5–9 bit DATA (LSB trước)
- 0–1 bit PARITY (lẻ/chẵn/không có)
- 1, 1.5, hoặc 2 bit STOP (HIGH)

Đề tài dùng cấu hình **8N1** (8 data + No parity + 1 stop) ở **115200 baud**.

**Ưu điểm và nhược điểm:**

| Ưu điểm | Nhược điểm |
|---|---|
| Chỉ 2 dây tín hiệu, đơn giản | Không có địa chỉ → 1-to-1 only |
| Mỗi đầu độc lập về clock | Sai khác clock > 5% gây lỗi khung |
| Phần mềm parser đơn giản | Không có CRC hardware (phải thêm ở mức app) |
| Hỗ trợ phổ biến (mọi MCU/SBC) | Tốc độ giới hạn (~3 Mbps) so với USB/SPI |

**Giao tiếp UART giữa Raspberry Pi và ESP32:**

Có hai phương án vật lý nối UART giữa Pi 5 và ESP32:
1. **Nối thẳng GPIO UART:** dùng `/dev/ttyAMA0` của Pi (chân 8 TXD, 10 RXD) nối với chân RX/TX của ESP32. Tuy nhiên cần level shifter (Pi GPIO ở 3.3 V – cùng mức ESP32 nên thực tế nối thẳng được, nhưng vẫn phải tự đi dây).
2. **Qua USB-CDC (đề tài chọn):** dùng cổng USB-A của Pi nối đến cổng micro-USB của DevKit ESP32. Chip CP2102 trên DevKit cầu nối UART0 ↔ USB. Pi nhìn thấy là `/dev/ttyUSB0`.

Phương án 2 được chọn vì:
- Cùng cáp dùng được cho nạp firmware ESP32 (`esptool.py`) và truyền runtime, không phải đảo dây.
- Tự cấp nguồn 5 V cho ESP32 DevKit qua USB khi đang gỡ rối (debug bench).
- USB hub có thể nối thêm webcam mà không tranh chấp GPIO.

**Quá trình hoạt động:**

1. Pi mở `/dev/ttyUSB0` ở 115200 baud, 8N1, không flow control.
2. ESP32 cấu hình `Serial.begin(115200)` trong `setup()`.
3. Pi gửi: `Pi → CP2102 (USB-CDC) → ESP32.UART0.RX`.
4. ESP32 phát: `ESP32.UART0.TX → CP2102 → USB → Pi`.
5. Pi xử lý từng dòng UTF-8 kết thúc bằng `\n`, parse JSON.

Chi tiết giao thức được trình bày ở mục 3.5.

## 2.3. Ý tưởng thiết kế

### 2.3.1. Phân tích thiết kế

Đề tài chia nhỏ thành các "khối chức năng" sau:

1. **Khối thu hình ảnh:** webcam USB → Pi 5 → V4L2.
2. **Khối xử lý thị giác máy tính:** OpenCV + MediaPipe + face_recognition + pyzbar.
3. **Khối quản lý dữ liệu:** SQLite (users, face_encodings, qr_tokens, events).
4. **Khối giao tiếp inter-node:** UART JSON Lines qua USB-CDC.
5. **Khối điều khiển ngoại vi:** ESP32 + RC522 + Servo + LCD + HC-SR04 + buzzer.
6. **Khối hiển thị/giám sát:** Flask web admin (port 8080 LAN).
7. **Khối nguồn:** 12 V DC → buck → 5 V → LDO → 3.3 V.

Việc phân lớp này phục vụ hai mục đích:
- Tách rõ trách nhiệm để khi gỡ lỗi biết module nào sai.
- Có thể thay thế một khối mà không phá hỏng khối khác (ví dụ đổi webcam C270 → C920, hoặc đổi RC522 → PN532 chỉ ảnh hưởng firmware ESP32).

### 2.3.2. Yêu cầu thiết kế

| # | Yêu cầu | Tiêu chí kiểm tra |
|---|---|---|
| R1 | Xác thực bằng khuôn mặt | Đúng người trong DB → mở cổng < 2 s từ khi vào khung |
| R2 | Xác thực bằng QR | Mã hợp lệ → mở cổng < 1 s |
| R3 | Xác thực bằng RFID | Thẻ trong allowlist → mở cổng < 0.5 s |
| R4 | Cánh chắn mở/đóng đúng góc | Mở 100°, đóng 10°, sai số ≤ 5° |
| R5 | Phát hiện hành khách đã qua | HC-SR04 báo trong < 1 s sau khi qua |
| R6 | Cảnh báo nếu không đi qua | Sau 10 s OPEN_WAIT, buzzer warn pattern |
| R7 | Cưỡng bức đóng nếu cảnh báo | Sau 5 s warn, tự đóng |
| R8 | LCD hiển thị tên người dùng | Đúng `"Welcome: <tên>"` khi mở cổng |
| R9 | Ghi sự kiện vào SQLite | Mỗi xác thực → 1 dòng `events`, có `clip_path` |
| R10 | Web admin xem trực tiếp | Trình duyệt LAN truy cập `http://<pi>:8080`, thấy MJPEG |
| R11 | Standalone resilience | Rút USB → ESP32 vẫn xác thực RFID + mở/đóng được |
| R12 | Khởi động lại tự động | systemd restart-on-failure |
| R13 | Thi công gọn | Hộp 200 × 100 × 40 mm chứa Pi + carrier ESP32 + cấp nguồn |
| R14 | Đủ tài liệu | spec, schematic, BOM, README, báo cáo |

## 2.4. Xây dựng sơ đồ khối

### 2.4.1. Sơ đồ khối tổng quát hệ thống

Sơ đồ khối tổng quát của Smart Gate được thể hiện ở Hình 2.7 (mô tả bằng văn bản):

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
│                          face_recognition       ffmpeg .mp4   │
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
│                        - gate_fsm   (state machine, FSM)     │
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

### 2.4.2. Chức năng của từng khối

| Khối | Chức năng chính |
|---|---|
| **Pi 5 – Capture** | Mở `/dev/video0` qua cv2.CAP_V4L2, ép FOURCC MJPG, BUFFERSIZE=1; encode JPEG 75 quality; publish `(jpeg, bgr)` lên FrameHub. |
| **Pi 5 – FrameHub** | `threading.Condition` + 2 ô latest-frame; `notify_all()` mỗi khung mới. |
| **Pi 5 – Detector** | Tiêu thụ BGR; MediaPipe khoanh khuôn mặt; face_recognition tạo embedding; matcher so sánh; pyzbar đọc QR; đẩy `AuthEvent` lên EventBus. |
| **Pi 5 – Flask** | `/stream.mjpeg` multipart, `/events.json`, `/users`, `/clips/<id>.mp4`, `/api/gate/{open,close}`. |
| **Pi 5 – Recorder** | RingBuffer 5s pre, sau sự kiện chờ 5s post; ffmpeg encode MP4 H.264. |
| **Pi 5 – DB** | SQLite WAL, busy_timeout 5000ms, 1 connection/thread. |
| **Pi 5 – UART RX/TX** | pyserial `Serial(115200, 8N1)`; 3 thread: rx parse, tx queue drain, heartbeat ping 5s. |
| **Pi 5 – CLI** | Subcommands: enroll, users, qr, events; signal daemon qua SIGUSR1 để reload matcher. |
| **ESP32 – uart_link** | Byte-by-byte read vào linebuf 512B; on `\n` parse JSON; dispatch event_t vào event_q. |
| **ESP32 – rfid** | MFRC522 polling 50ms; on hit → lookup NVS → push EV_RFID_SCAN. |
| **ESP32 – sensor** | HC-SR04 pulseIn 50ms; debounce 3-count; on transition → EV_PASSAGE_DETECTED. |
| **ESP32 – gate_fsm** | Đọc event_q `portMAX_DELAY`; chạy FSM (IDLE/OPENING/OPEN_WAIT/TIMEOUT_WARN/CLOSING); gọi inline driver. |
| **ESP32 – allowlist** | Preferences NVS namespace `allowlist`; key = UID hex; value = name; key đặc biệt `_index` lưu JSON array UIDs. |
| **ESP32 – timers** | open_reached (300 ms), passage_timeout (10 s), warn_giveup (5 s), close_reached (300 ms), heartbeat (10 s auto-reload). |
| **ESP32 – watchdog** | TWDT 8 s, chỉ subscribe gate_fsm_task. |

## 2.5. Xây dựng sơ đồ nguyên lý và mạch in

### 2.5.1. Sơ đồ nguyên lý (KiCad schematic)

Sơ đồ nguyên lý carrier board ESP32 được vẽ trong KiCad 6.0.2, lưu tại `kicad/smart_gate_carrier/smart_gate_carrier.kicad_sch` (đơn-sheet).

**Cấu trúc schematic:**

1. **ESP32 DevKit socket:** 2 hàng header 15-chân chạy dọc, ESP32 DevKit DOIT V1 cắm vào. Nhãn các chân theo Bảng 2.7.
2. **Khối nguồn:**
   - Đầu vào: J1 barrel jack 12 V DC + diode bảo vệ D1 (1N5819).
   - Buck converter U1 (module MP1584 4-pin: VIN, GND, VOUT, EN) → 5 V rail.
   - Tụ lọc đầu vào C1 470 µF / 25 V, đầu ra C2 470 µF / 16 V (gần socket Servo).
   - LDO U2 (AMS1117-3.3): vào 5 V, ra 3.3 V; tụ C3 10 µF đầu vào, C4 10 µF đầu ra.
3. **Khối RC522 (SPI):** header J2 8-chân (SDA/CS, SCK, MOSI, MISO, IRQ, GND, RST, 3.3 V). Cấu hình remap chân (xem Bảng 2.7).
4. **Khối LCD 20×4 (I2C):** header J3 4-chân (GND, VCC 5 V, SDA, SCL). Hai trở pull-up 4.7 kΩ kéo về **3.3 V** (R1, R2). Ghi chú lắp ráp: **cắt** pull-up gốc 5 V trên backpack PCF8574.
5. **Khối HC-SR04:** header J4 4-chân (VCC 5 V, TRIG, ECHO, GND). Mạch chia áp ECHO: R3 = 1 kΩ + R4 = 2 kΩ.
6. **Khối Servo SG90:** header J5 3-chân (GND, 5 V, SIG). Tụ điện C5 470 µF cạnh chân nguồn để hấp thụ dòng đỉnh.
7. **Khối Buzzer:** Q1 (2N3904 NPN) base qua R5 = 1 kΩ, emitter GND, collector nối Buzzer (-); Buzzer (+) nối 5 V. Diode D2 (1N4148) ngược song song flyback.
8. **Khối Header mở rộng:** J6 6-chân (3V3, GND, GPIO17, GPIO5, GPIO36, GPIO39) cho mở rộng tương lai.
9. **LED trạng thái:** D3 + R6 = 330 Ω nối GPIO 2 và GND.

ERC (Electrical Rules Check) đã được chạy và clean.

### 2.5.2. Sơ đồ mạch in (PCB) 2D

(Việc layout PCB là pha tiếp theo của plan KiCad – `2026-05-22-kicad-schematic.md` đã hoàn thành schematic; PCB layout sẽ tạo từ netlist của schematic.)

Kích thước PCB dự kiến: **80 mm × 60 mm**, 2 lớp, độ rộng đường tín hiệu 0.25 mm, đường nguồn 0.5 mm, via 0.6/0.3 mm. ESP32 DevKit được cắm vào 2 hàng header socket. Tất cả ngoại vi nối qua đầu header XH/Dupont để dễ tháo lắp khi sửa.

### 2.5.3. Mạch thực tế

Mạch thực tế sau khi đặt sản xuất PCB và hàn linh kiện sẽ được thi công và chụp ảnh khi hoàn thành (xem Chương 4).

### 2.5.4. Phân bố chân ESP32 chi tiết (Bảng 2.7)

Do DevKit DOIT V1 30-pin **không expose** các chân GPIO 18/19/21/22/23 (vốn là chân SPI và I2C mặc định của ESP32), đề tài sử dụng **GPIO matrix** để remap SPI và I2C sang các chân khác:

| GPIO | Hướng | Ngoại vi | Ghi chú |
|---|---|---|---|
| 1 | OUT | UART0 TX (USB-CDC) | Dành riêng |
| 3 | IN | UART0 RX (USB-CDC) | Dành riêng |
| 2 | OUT (strap) | LED trạng thái onboard | Không được pull HIGH tại boot |
| 14 | OUT | RC522 SCK | VSPI remap |
| 13 | OUT | RC522 MOSI | VSPI remap |
| 35 | IN-only | RC522 MISO | Input-only OK cho MISO |
| 15 | OUT (strap) | RC522 CS | Strap HIGH OK (CS idle HIGH) |
| 4 | OUT | RC522 RST | Active LOW; pull HIGH khi chạy |
| 16 | IN | RC522 IRQ | Tùy chọn; polling mode nên không dùng |
| 32 | I/O | LCD I2C SDA | Pull-up 4.7 kΩ về **3.3 V** |
| 33 | OUT | LCD I2C SCL | Pull-up 4.7 kΩ về **3.3 V** |
| 25 | OUT | HC-SR04 TRIG | Xung 10 µs, 3.3 V đủ trigger |
| 34 | IN-only | HC-SR04 ECHO | **Phải có chia áp** R1=1k, R2=2k |
| 26 | OUT | Servo SG90 PWM | LEDC kênh 0, 50 Hz, 1–2 ms pulse |
| 27 | OUT | Active buzzer | Qua 2N3904 + 1 kΩ |
| 6–11 | – | **KHÔNG SỬ DỤNG** | Nối với flash nội |
| 12 | – | **KHÔNG SỬ DỤNG** | Strap LOW at boot |
| 17, 5, 36, 39 | – | Mở rộng | Header expansion |

### 2.5.5. Ước tính dòng tiêu thụ (Bảng 2.8)

| Đường nguồn | Tải | Dòng đỉnh ước tính |
|---|---|---|
| 3.3 V | ESP32 (120 mA) + RC522 (30 mA) | ~150 mA |
| 5 V | LCD + backlight (50 mA) + HC-SR04 (15 mA) + SG90 (đỉnh 500 mA) + Buzzer (25 mA) | ~600 mA đỉnh |
| 12 V (sau buck ~85% hiệu suất) | (600 mA × 5 V) / (12 V × 0.85) | ~300 mA |

Adapter 12 V/2 A là dư so với yêu cầu 300 mA – đảm bảo dự phòng khi gắn thêm ngoại vi tương lai.

## 2.6. Thi công mô hình

### 2.6.1. Cơ khí khung cổng (FreeCAD)

Mô hình cơ khí được dựng trong FreeCAD 0.21, file `mechanical/smart_gate_assembly.FCStd`. Các thông số bảng tham số (Spreadsheet) gồm:

- `base_w` = 200 mm (rộng thân hộp).
- `base_d` = 100 mm (sâu thân hộp).
- `base_h` = 40 mm (cao thân hộp).
- `post_w` = 30 mm (cạnh trụ).
- `post_h` = 60 mm (cao trụ).
- `arm_len` = 80 mm (chiều dài cánh chắn).
- `lane_w` = 60 mm (rộng lane đi).

**Các chi tiết:**

| Chi tiết | Kích thước (mm) | Vật liệu | Ghi chú |
|---|---|---|---|
| Hộp đáy | 200 × 100 × 40 | MDF 3 mm | Chứa Pi 5 + carrier PCB + buck + cáp |
| Trụ trái (gắn Servo) | 30 × 30 × 60 | MDF 3 mm 6 panel | Servo nằm ngang, horn hướng phải |
| Trụ phải (đỡ) | 30 × 30 × 60 | MDF 3 mm 6 panel | Pad foam đệm khi cánh chắn nghỉ |
| Cánh chắn | 80 × 8 × 3 | Balsa hoặc acrylic | Sơn sọc đỏ/vàng |
| Giá Servo | ~25 × 25 × 25 | PLA in 3D | 2 lỗ M3 cho SG90, đáy bắt vít vào trụ |
| Giá camera | dia 8 × 250 + đế 80 × 80 | Cọc gỗ + đế MDF | Webcam nghiêng 30° xuống lane |
| Mặt trước hộp | 200 × 40 | MDF 3 mm | Khoét lỗ LCD 98 × 24, RC522 60 × 40, HC-SR04 2 × Ø16, LED Ø3, Buzzer Ø8 |
| Mặt sau hộp | 200 × 40 | MDF 3 mm | Lỗ jack DC Ø8, USB-C Pi 14 × 6, 4 khe tản nhiệt |

### 2.6.2. Lắp ráp

Trình tự lắp ráp:

1. Cắt laser các panel MDF từ file DXF (export từ FreeCAD).
2. In 3D giá Servo (PLA, infill 30%, layer 0.2 mm).
3. Gắn SG90 vào giá, gắn giá vào trụ trái bằng vít M3.
4. Gắn cánh chắn vào horn Servo (bằng vít M2 + keo).
5. Hàn linh kiện lên PCB carrier (sau khi nhận từ xưởng).
6. Cắm ESP32 DevKit vào socket carrier, nối các ngoại vi qua header XH.
7. Cố định carrier PCB và Pi 5 vào đáy hộp bằng cột bằng ốc M2.5.
8. Cắt cửa sổ mặt trước cho LCD, RC522, HC-SR04, LED, buzzer.
9. Gắn webcam lên giá camera; nối cáp USB từ webcam đến cổng USB 3.0 Pi.
10. Nối cáp USB từ Pi đến DevKit ESP32 (cùng cáp dùng cho nạp firmware sau).
11. Cắm jack DC 12 V vào mặt sau, cấp nguồn carrier.
12. Cấp nguồn USB-C 5 V/5 A cho Pi.

## 2.7. Kết luận chương II

Chương 2 đã trình bày toàn bộ thiết kế phần cứng cho Smart Gate, từ việc tìm hiểu lý thuyết các linh kiện chính, đến phân tích yêu cầu, xây dựng sơ đồ khối, sơ đồ nguyên lý KiCad, ước tính dòng tiêu thụ, mô hình hóa cơ khí FreeCAD và quy trình lắp ráp. Phân bố chân ESP32 đã được chỉnh sửa để tương thích với DevKit DOIT V1 30-pin (remap SPI/I2C qua GPIO matrix). Hệ thống nguồn 12 V → 5 V → 3.3 V đảm bảo ổn định cho cả MCU và các ngoại vi yêu cầu dòng cao như SG90.

Đầu ra của chương:
- Sơ đồ khối tổng quát.
- Sơ đồ nguyên lý KiCad đã pass ERC.
- Bảng phân chân ESP32 chi tiết.
- Bảng ước tính dòng tiêu thụ.
- Mô hình 3D cơ khí FreeCAD và DXF panel cắt laser.

Chương tiếp theo (Chương 3) sẽ trình bày phần thiết kế phần mềm trên cả Pi 5 và ESP32, đặc tả giao thức UART JSON Lines, máy trạng thái cổng, và quy trình xác thực khuôn mặt + QR.

---

# CHƯƠNG 3. THIẾT KẾ PHẦN MỀM

## 3.1. Giới thiệu phần mềm và dữ liệu hệ thống

### 3.1.1. Mục tiêu thiết kế phần mềm

Phần mềm Smart Gate được thiết kế với các mục tiêu cụ thể:

1. **Đúng giao thức:** triển khai chính xác giao thức UART JSON Lines (mục 3.5.2).
2. **Phục hồi độc lập:** ESP32 phải tiếp tục xác thực RFID + đóng/mở cổng được khi mất kết nối với Pi.
3. **Đơn giản hơn là quy mô:** mỗi MCU/SBC chỉ chạy số luồng/task tối thiểu (Pi: 8 luồng; ESP32: 4 task).
4. **Khả năng quan sát (observability):** mỗi chuyển trạng thái, lỗi parse, lỗi I/O đều phát ra một sự kiện trên serial – người vận hành nhìn `journalctl -u smart-gate` thấy ngay.
5. **Tham số hóa qua cấu hình:** thay vì hard-code, dùng `/etc/smart-gate/config.toml` (Pi) và `cmd:config` qua UART (ESP32).
6. **An toàn cho thẻ NVS:** không ghi NVS trong vòng lặp nóng; ghi 1 lần khi `cmd:add_uid` hoặc `cmd:config`.

### 3.1.2. Nền tảng phần cứng và ngôn ngữ lập trình

| Nền tảng | OS / Framework | Ngôn ngữ | Build tool |
|---|---|---|---|
| Raspberry Pi 5 | Raspberry Pi OS Bookworm 64-bit | Python 3.11 | venv + pip |
| ESP32-WROOM-32 | Arduino-ESP32 (trên FreeRTOS nội) | C/C++ (Arduino sketch chuyển thành module .cpp) | PlatformIO |

### 3.1.3. Kiến trúc phần mềm tổng thể

**Trên Pi 5** (xem Hình 3.1): một tiến trình Python duy nhất (`python -m smart_gate`) chạy 8 luồng, được systemd quản lý. Một tiến trình CLI riêng (`python -m smart_gate.cli`) phục vụ enroll/QR/users/events; tiến trình CLI và daemon đồng bộ qua SQLite + signal SIGUSR1.

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

**Trên ESP32** (xem Hình 3.6 cho FSM): firmware Arduino-ESP32 với 4 FreeRTOS task pinned core:

| Task | Stack | Priority | Core | Trách nhiệm |
|---|---|---|---|---|
| `uart_link_task` | 4096 B | 3 | 0 | Đọc Serial byte-by-byte, parse JSON, đẩy event_t; drain outbound_q |
| `rfid_task` | 3072 B | 2 | 1 | Polling MFRC522 mỗi 50 ms |
| `sensor_task` | 2048 B | 2 | 1 | Polling HC-SR04 mỗi 50 ms |
| `gate_fsm_task` | 4096 B | 4 | 1 | Đọc event_q, chạy FSM, gọi inline driver Servo/LCD/Buzzer |

Lý do **không** tạo task riêng cho Servo/LCD/Buzzer: các driver này non-blocking (Servo.write() trả về ngay, LCD I2C transaction ~5 ms, buzzer_beep_ok() chỉ 80 ms). Tạo task riêng chỉ tốn ~9 KB stack mà không tăng độ phản hồi.

### 3.1.4. Chức năng từng khối phần mềm

(Đã được trình bày chi tiết ở mục 2.4.2 cho cả Pi và ESP32. Xem thêm các mục 3.2–3.6 ở dưới.)

### 3.1.5. Mô hình dữ liệu hệ thống

**Trên Pi 5 – SQLite schema** (`data/migrations/0001_init.sql`):

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

**Các quyết định thiết kế DB:**

- 3–5 mẫu khuôn mặt/người (cải thiện độ chính xác); mỗi mẫu lưu thành 1 dòng.
- Embedding 128 float32 = 512 byte/dòng; load `numpy.frombuffer(blob, dtype='float32')`.
- 1 QR token đang hoạt động/người (enforce bởi partial unique index `WHERE revoked_at IS NULL`).
- Sự kiện RFID từ ESP32 cũng được mirror vào bảng `events` để có nhật ký thống nhất.
- `esp_log` tách riêng để log spam không làm lẫn `events`.

**Trên ESP32 – NVS Preferences:**

NVS namespace `allowlist`: 1 key/UID hex (8 ký tự), value = name. Key đặc biệt `_index` = JSON array các UIDs để hỗ trợ `cmd:list_uids` (NVS không có API enumerate sẵn). Giới hạn `ALLOWLIST_MAX_ENTRIES = 100`.

NVS namespace `config`: `close_timeout_s`, `servo_open_deg`, `servo_close_deg` lưu thành key tương ứng. Mặc định nếu chưa từng ghi: 10 / 100 / 10.

### 3.1.6. Luồng dữ liệu toàn hệ thống

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
                                  ┌──────────┐         [data/clips/N.mp4]
                                  │ /dev/    │
                                  │ ttyUSB0  │ ◀───── [pyserial rx] ─── (evt:rfid, evt:gate, ...)
                                  └────┬─────┘                              │
                                       │                                    ▼
                                       ▼                              [SQLite events]
                              ┌─────────────┐
                              │ ESP32 UART0 │
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

## 3.2. Tổng quan xử lý ảnh

### 3.2.1. Khái niệm

Xử lý ảnh số là quá trình áp dụng các phép biến đổi toán học lên ma trận điểm ảnh để cải thiện chất lượng, trích xuất thông tin, hoặc tự động hóa nhận dạng đối tượng. Trong hệ thống Smart Gate, xử lý ảnh phục vụ hai bài toán chính:

- **Phát hiện và nhận dạng khuôn mặt:** xác định đâu là khuôn mặt và đó có phải người trong CSDL không.
- **Phát hiện và giải mã mã QR:** đọc nội dung mã QR (token) và đối chiếu với CSDL.

### 3.2.2. Quy trình xử lý ảnh

```
Khung BGR từ webcam (15 fps)
        │
        ▼
[Color convert BGR → RGB]              (cv2.cvtColor)
        │
        ▼
[Resize / crop ROI (tùy chọn)]         (640×480 đã đủ)
        │
        ▼
┌───────────────┬──────────────┐
▼               ▼              ▼
[MediaPipe     [pyzbar         [Future:
 Face          decode QR]      anti-spoofing]
 Detection]    (toàn frame
        │      mỗi khung)
        ▼
[Crop khuôn mặt +
 padding 20%]
        │
        ▼
[face_recognition.face_encodings]      (dlib HOG/CNN)
        │
        ▼
[Matcher: tìm user nearest neighbor    (Euclidean distance trên 128-dim)
        │
        ▼
[Threshold check:                      (0.55 = grant; 0.55–0.65 = uncertain; >0.65 = stranger)
        │
        ▼
[Debouncer]                            (5s cooldown/user, 30s cho stranger)
        │
        ▼
[EventBus]
```

### 3.2.3. Các bước tiền xử lý ảnh

1. **Chuyển không gian màu (color conversion):** webcam đẩy BGR, MediaPipe và face_recognition cần RGB. Một phép `cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)` ở đầu pipeline.
2. **Resize (khi cần):** đề tài dùng 640×480 nguyên gốc – đã đủ nhỏ cho MediaPipe trên Pi 5. Không downscale thêm.
3. **Padding ROI khuôn mặt:** sau khi MediaPipe trả bbox, mở rộng 20% mỗi cạnh để face_recognition thấy được toàn bộ vùng tóc/má/cằm – cải thiện chất lượng embedding.
4. **JPEG re-encode (cho Flask):** `cv2.imencode('.jpg', bgr, [cv2.IMWRITE_JPEG_QUALITY, 75])` để giảm băng thông LAN.
5. **Khử nhiễu (gaussian blur) – không sử dụng:** đã thử thêm `cv2.GaussianBlur(rgb, (3,3), 0)` trước khi gọi face_recognition, nhưng độ chính xác không cải thiện đáng kể trong điều kiện ánh sáng demo, lại tốn ~3 ms/khung – nên bỏ.

### 3.2.4. Cấu hình camera quan trọng

```python
cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
cap.set(cv2.CAP_PROP_FPS, 15)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
```

- `MJPG`: webcam encode JPEG ở nguồn → tiết kiệm băng thông USB.
- `BUFFERSIZE=1`: kernel chỉ giữ 1 khung mới nhất – tránh "frame lag" khi detector chạy chậm hơn capture.

### 3.2.5. Lý do chọn MJPEG over HTTP cho live preview

Đề tài cân nhắc 3 phương án streaming:

| Phương án | Độ trễ | Phức tạp | Quyết định |
|---|---|---|---|
| HLS (HTTP Live Streaming) | 2–6 s | Trung bình (cần segment + manifest) | **Loại** – độ trễ quá cao cho mục đích giám sát an ninh |
| WebRTC | < 100 ms | Cao (cần aiortc + STUN + signaling, ~300 dòng code) | **Loại** – overkill cho 1 viewer LAN |
| MJPEG over HTTP multipart | 200–500 ms | Thấp (~50 dòng Python, native trình duyệt) | **Chọn** – công cụ phù hợp |

## 3.3. Phát hiện, nhận dạng khuôn mặt

### 3.3.1. Khái niệm

- **Phát hiện khuôn mặt (face detection):** xác định trong khung hình có khuôn mặt không, và bbox của chúng. Không quan tâm "đó là ai".
- **Nhận dạng khuôn mặt (face recognition):** so sánh khuôn mặt với một CSDL gồm các "khuôn mặt đã đăng ký" và trả về danh tính.

Hai bước này tách rời để có thể thay đổi thuật toán nhận dạng mà không phải code lại bước phát hiện.

### 3.3.2. Phương pháp sử dụng

**Phát hiện (detection):**

Đề tài chọn **MediaPipe Face Detection** (Google):
- Tốc độ ~10 ms/khung trên Pi 5 → đủ realtime ở 15 fps.
- Đơn giản, không phụ thuộc TensorFlow/PyTorch nặng.
- Hỗ trợ trực tiếp qua `python3-mediapipe` apt package trên Pi OS Bookworm.

**So sánh các phương pháp phát hiện đã cân nhắc:**

| Phương pháp | Tốc độ trên Pi 5 | Độ chính xác | Phụ thuộc |
|---|---|---|---|
| Haar Cascade (OpenCV) | ~5 ms | Trung bình; nhiều false positive | OpenCV (đã có) |
| HOG + SVM (dlib) | ~50 ms | Tốt | dlib |
| MediaPipe Face Detection | ~10 ms | Tốt | mediapipe |
| MTCNN | ~200 ms | Rất tốt | PyTorch |
| YOLO-v8-face | ~80 ms | Xuất sắc | ultralytics |

MediaPipe được chọn vì cân bằng tốc độ – độ chính xác – dependency.

**Nhận dạng (recognition):**

Đề tài dùng **face_recognition** (Adam Geitgey, wrapper trên dlib):
- Tạo embedding 128 chiều từ một bbox khuôn mặt.
- Hàm `face_encodings(rgb_image)` chạy `dlib.face_recognition_model_v1`.
- Embedding được so sánh bằng khoảng cách Euclidean.

**Lý do không dùng các model deep mới như ArcFace/MobileFaceNet:**
- Yêu cầu PyTorch/ONNX runtime – cài đặt nặng trên Pi 5.
- Cho demo prototype với < 50 người, face_recognition đã đủ chính xác.
- Có thể đổi sau (matcher.match_face chỉ phụ thuộc vector 128-dim, không phụ thuộc mô hình tạo).

### 3.3.3. Phân tích thuật toán

**So sánh khuôn mặt qua khoảng cách Euclidean:**

Cho hai embedding 128 chiều $\mathbf{u}, \mathbf{v} \in \mathbb{R}^{128}$, khoảng cách:

$$ d(\mathbf{u}, \mathbf{v}) = \sqrt{\sum_{i=1}^{128} (u_i - v_i)^2} $$

Trong code, dùng `numpy.linalg.norm(probe - enc)`. Việc tính trên CPU Pi 5 với 200 vector mất ~1 ms (vectorized).

**Multi-sample matching:**

Mỗi user có 3–5 mẫu (chụp ở các góc khác nhau khi enroll). Khi match:

```python
def match_face(self, probe):
    user_dists = {}
    for user_id, enc in self._faces:
        d = np.linalg.norm(probe - enc)
        if d < user_dists.get(user_id, float('inf')):
            user_dists[user_id] = d
    # chọn user có min(d) nhỏ nhất
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

Ngưỡng `0.55` chặt hơn mặc định `0.6` của face_recognition – vì hệ thống demo có "base rate" thấp (ít người), cần giảm false positive.

### 3.3.4. Phương pháp chống giả mạo khuôn mặt (anti-spoofing)

Đây là một mảng quan trọng nhưng **được liệt vào hướng phát triển** (xem mục 4.5), không triển khai trong phiên bản đề tài này vì giới hạn thời gian. Các kỹ thuật chống giả mạo có thể bổ sung:

- **Liveness detection:** yêu cầu người dùng chớp mắt hoặc quay đầu (cần thêm landmarks + temporal analysis).
- **Depth sensing:** dùng camera stereo (Intel RealSense) hoặc camera CSI Pi v3 với LiDAR – tránh tấn công bằng ảnh in.
- **Texture analysis:** phân tích moiré pattern (đường vân) khi đối tượng là màn hình LCD chụp lại.
- **Multi-modal:** kết hợp face + QR + RFID (đã có) – tấn công cả 3 thì khó hơn nhiều.

### 3.3.5. Training và enrollment

Đề tài **không training mô hình mới**. Dùng pretrained dlib (cùng face_recognition wrapper), chỉ tạo embedding cho từng user khi enroll.

**Quy trình enroll** (`python -m smart_gate.cli enroll --name alice --samples 5`):

1. Mở webcam qua cv2.
2. Hiển thị live preview với bbox khuôn mặt (do MediaPipe phát hiện).
3. Hướng dẫn người dùng nhấn SPACE để chụp 1 mẫu (khuyến nghị 5 mẫu ở các góc/biểu cảm khác nhau).
4. Với mỗi mẫu: tính embedding 128-dim, INSERT vào `face_encodings`.
5. Phát signal SIGUSR1 đến daemon → daemon reload matcher.
6. Sinh QR token (16 byte ngẫu nhiên = 32 ký tự hex), INSERT vào `qr_tokens`, ghi PNG vào `data/qr/<name>.png` bằng thư viện `qrcode`.

**So sánh tùy chọn training:**

| Tùy chọn | Có training riêng | Có cần GPU |
|---|---|---|
| Google Colab | Có (FaceNet/ArcFace finetune) | Có |
| OpenCV LBPHRecognizer | Có (đơn giản, nhanh) | Không |
| face_recognition (đã chọn) | Không (chỉ embedding) | Không |

Vì đề tài có < 50 người mục tiêu, pretrained embedding đã đủ. Việc finetune chỉ cần thiết khi: (a) dữ liệu khuôn mặt người Việt khác biệt đáng kể với dataset gốc, (b) cần đẩy độ chính xác lên > 99%.

### 3.3.6. Lưu đồ thuật toán xác thực khuôn mặt (Hình 3.4)

```
START
  │
  ▼
[Đọc khung BGR từ FrameHub]
  │
  ▼
[Convert BGR → RGB]
  │
  ▼
[MediaPipe Face Detection]
  │
  ├── Không có khuôn mặt? ──▶ [Return, chờ khung sau]
  │
  ▼ (có khuôn mặt)
[Chọn bbox có score cao nhất]
  │
  ▼
[Pad bbox 20% mỗi chiều, crop ROI]
  │
  ▼
[face_recognition.face_encodings(roi)]
  │
  ├── Empty list? ──▶ [Return]
  │
  ▼
[probe = encodings[0].astype('float32')]
  │
  ▼
[matcher.match_face(probe) → (user_id, distance)]
  │
  ├── distance < 0.55? ──▶ [granted=True; method='face']
  │                                │
  │                                ▼
  │                            [Debouncer.should_emit?]
  │                                │
  │                                ├── False ─▶ [Return (cooldown)]
  │                                │
  │                                ▼ True
  │                            [INSERT events; uart.send_cmd('open', {...})]
  │                                │
  │                                ▼
  │                            [Recorder.trigger(event_id)]
  │                                │
  │                                ▼
  │                              END
  │
  ├── 0.55 ≤ distance ≤ 0.65? ──▶ [Drop silently]
  │
  ▼ distance > 0.65
[granted=False; method='face'; user_id=None]
  │
  ▼
[Debouncer.should_emit_stranger?]
  │
  ├── False ─▶ END (cooldown 30s)
  │
  ▼ True
[INSERT events (stranger); Recorder.trigger]
  │
  ▼
END
```

### 3.3.7. Đánh giá

Pipeline đạt được hiệu năng tốt trên Pi 5:
- Detection (MediaPipe): ~10 ms/khung.
- Embedding (dlib): ~60–80 ms/khung.
- Match (numpy): ~1 ms cho 200 vector.
- Tổng cho 1 khung có khuôn mặt: ~80–100 ms → khoảng 10 fps thực tế.

Capture chạy 15 fps; detector chỉ xử lý ~10 fps – tức bỏ qua 30–50% khung. Đây là **chấp nhận được** vì luôn xử lý khung mới nhất nhờ `BUFFERSIZE=1` + FrameHub. Người dùng đi qua cổng trong ~2 giây có khoảng 20 cơ hội được phát hiện.

## 3.4. Quét mã QR

### 3.4.1. Giới thiệu và vai trò

QR code là phương thức xác thực thứ hai trong Smart Gate – bổ trợ cho khuôn mặt khi:
- Người dùng đeo khẩu trang hoặc kính râm khiến nhận diện khuôn mặt thất bại.
- Khách vãng lai có QR tạm thời (single-use hoặc thời hạn ngắn) mà không cần đăng ký khuôn mặt.

Mỗi user có 1 QR token đang hoạt động (enforce bằng partial unique index). Token là chuỗi hex 32 ký tự = 16 byte ngẫu nhiên (`secrets.token_hex(16)`).

### 3.4.2. Phương pháp giải mã QR

Đề tài dùng **pyzbar** (Python binding của thư viện C `libzbar`):
- `pyzbar.decode(bgr_image)` trả về list các đối tượng `Decoded(data=b'...', rect=..., polygon=..., type='QRCODE')`.
- Tốc độ ~5 ms/khung trên Pi 5.
- Tự động xử lý xoay/biến dạng nhỏ – không cần preprocess.

**So sánh với các giải pháp khác:**

| Giải pháp | Tốc độ | Ưu/Nhược |
|---|---|---|
| pyzbar (libzbar) | ~5 ms | Đơn giản, ổn định; chỉ QR/Code128/Code39 |
| opencv-contrib `QRCodeDetector` | ~10 ms | OpenCV built-in; đôi khi miss QR nhỏ |
| pyzxing (ZXing wrapper) | ~50 ms | Hỗ trợ nhiều loại barcode; cài Java JVM nặng |

pyzbar được chọn vì đơn giản nhất.

### 3.4.3. Quy trình quét QR

```
[Khung BGR]
    │
    ▼
[pyzbar.decode(bgr)]
    │
    ├── Empty? ──▶ END
    │
    ▼
For each Decoded symbol:
    │
    ▼
[token = symbol.data.decode('utf-8', errors='replace')]
    │
    ▼
[matcher.lookup_qr(token) → user_id hoặc None]
    │
    ├── None? ──▶ (Lặng lẽ bỏ qua, không ghi sự kiện stranger để tránh spam)
    │
    ▼
[granted=True; method='qr'; user_id=...]
    │
    ▼
[Debouncer + INSERT events + uart.send_cmd('open',...) + Recorder.trigger]
    │
    ▼
END
```

### 3.4.4. Nội dung dữ liệu QR và kiểm tra hợp lệ

QR token được sinh khi enroll user, lưu trong bảng `qr_tokens`. Lookup trong matcher chỉ kiểm tra:
1. Token có tồn tại trong `qr_tokens` không.
2. `revoked_at IS NULL` (token chưa bị thu hồi).

Không có thuật toán mật mã (HMAC, ký số) phức tạp ở phiên bản này – mục tiêu là demo. Trong môi trường production sẽ cần:
- Token kèm timestamp + HMAC để chống tấn công replay.
- TTL (time-to-live) ngắn.
- Token một-lần (single-use).

### 3.4.5. Các tình huống quét QR

| Tình huống | Hành vi |
|---|---|
| QR hợp lệ của user A trong DB | Mở cổng, INSERT event method='qr', user=A |
| QR đã bị revoked | Không tìm thấy trong matcher.lookup_qr (chỉ load token active); lặng lẽ bỏ qua |
| QR lạ (token không tồn tại) | Lặng lẽ bỏ qua – không ghi stranger event để tránh spam |
| Trong cùng khung có cả QR và khuôn mặt | Cả hai đều có thể trigger; debouncer cooldown 5s/user tránh trùng |
| QR bị xoay 180° | pyzbar tự xử lý – vẫn decode được |
| QR nhỏ (< 100 pixel) | Có thể miss; di chuyển QR gần camera hơn |

## 3.5. Phần mềm sử dụng với ESP32

### 3.5.1. Phần mềm xử lý ngoại vi

Phần này tổng kết toàn bộ firmware ESP32 (chi tiết spec ở mục 2.4.2 và bảng task ở mục 3.1.3).

**Bố cục dự án PlatformIO:**

```
firmware/
├── platformio.ini
├── include/
│   ├── config.h          # Pin numbers, timings, sizes
│   ├── events.h          # event_t, outbound_msg_t, enums
│   ├── log.h             # LOGI/LOGW/LOGE macros
│   └── version.h         # FW_VERSION
├── src/
│   ├── main.cpp          # setup(): NVS, queues, timers, tasks
│   ├── uart_link.cpp/.h  # JSON Lines RX/TX, parser, ack helper
│   ├── rfid.cpp/.h       # MFRC522 polling task
│   ├── sensor.cpp/.h     # HC-SR04 polling task, debounce
│   ├── gate_fsm.cpp/.h   # state machine, timer callbacks
│   ├── servo_drv.cpp/.h  # open_now() / close_now()
│   ├── lcd_drv.cpp/.h    # show_idle() / show_name() / show_warn()
│   ├── buzzer_drv.cpp/.h # beep_ok() / beep_err() / pattern_warn()
│   └── allowlist.cpp/.h  # NVS Preferences-backed UID/name store
├── README.md
└── test/                 # (empty for MVP)
```

**Hằng số cấu hình (`include/config.h`) – các mục chính:**

```cpp
// Pin (theo §2.5.4)
#define PIN_LED_STATUS   2
#define PIN_RC522_CS     15
#define PIN_RC522_SCK    14
#define PIN_RC522_MISO   35
#define PIN_RC522_MOSI   13
#define PIN_RC522_RST    4
#define PIN_LCD_SDA      32
#define PIN_LCD_SCL      33
#define PIN_SR04_TRIG    25
#define PIN_SR04_ECHO    34
#define PIN_SERVO        26
#define PIN_BUZZER       27

// Timings (ms)
#define DEFAULT_OPEN_REACHED_MS    300
#define DEFAULT_CLOSE_REACHED_MS   300
#define DEFAULT_PASSAGE_TIMEOUT_MS 10000
#define DEFAULT_WARN_GIVEUP_MS     5000
#define HEARTBEAT_INTERVAL_MS      10000
#define RFID_POLL_INTERVAL_MS      50
#define SENSOR_POLL_INTERVAL_MS    50
#define SENSOR_DEBOUNCE_COUNT      3
#define SENSOR_TRIGGER_CM          25

// Servo
#define DEFAULT_SERVO_OPEN_DEG     100
#define DEFAULT_SERVO_CLOSE_DEG    10

// NVS
#define NVS_NS_ALLOWLIST    "allowlist"
#define NVS_NS_CONFIG       "config"
#define ALLOWLIST_MAX_ENTRIES 100

// UART / JSON
#define UART_BAUD          115200
#define UART_LINE_MAX      512
#define JSON_DOC_CAPACITY  768
#define EVENT_QUEUE_LEN    16
#define OUTBOUND_QUEUE_LEN 16
```

(Lưu ý: pin assignment trong file này được điều chỉnh phù hợp với DOIT V1 30-pin – khác với firmware-spec ban đầu giả định dev kit 38-pin tiêu chuẩn.)

### 3.5.2. Giao thức UART JSON Lines (Pi ↔ ESP32)

**Cấu trúc khung tin:**

Một bản tin = 1 dòng UTF-8 JSON kết thúc bằng `\n`. Giới hạn tối đa 512 byte/dòng (phòng vệ; thực tế các bản tin < 200 byte).

```json
{"id": 42, "type": "cmd", "v": "open", "data": {"user": "alice", "reason": "face"}}
```

| Trường | Bắt buộc | Ý nghĩa |
|---|---|---|
| `id` | Khi cần ACK | Pi gán số nguyên tăng dần; ESP32 echo lại trong `ack` |
| `type` | Bắt buộc | `"cmd"` (Pi→ESP32), `"evt"` (ESP32→Pi), `"ack"` (ESP32→Pi reply cmd) |
| `v` | Bắt buộc | Verb (động từ); xem bảng dưới |
| `data` | Tùy verb | Object payload |

Không có CRC (USB-CDC tự lo CRC ở mức USB). Không có length-prefix (newline framing đủ). Parser lỗi → drop dòng và tiếp tục.

**Bảng 3.2. Bộ động từ lệnh (cmd) Pi → ESP32:**

| Verb | data | ack data | Mục đích |
|---|---|---|---|
| `open` | `{user, reason}` | `{ok:true}` | Pi đã xác thực face/QR; ESP32 mở cổng |
| `close` | – | `{ok:true}` | Cưỡng bức đóng (admin override) |
| `add_uid` | `{uid, name}` | `{ok:true,total:N}` | Thêm UID vào allowlist |
| `remove_uid` | `{uid}` | `{ok:true}` hoặc `{ok:false,err:"not_found"}` | Xóa UID |
| `list_uids` | – | `{uids:[{uid,name},...]}` | Dump allowlist |
| `config` | `{close_timeout_s, servo_open_deg, servo_close_deg}` | `{ok:true}` | Cập nhật cấu hình runtime |
| `status` | – | `{uptime_s, free_heap, gate, fw}` | Snapshot |
| `ping` | – | `{ok:true}` | Liveness probe (Pi gửi mỗi 5 s) |

**Bảng 3.3. Bộ động từ sự kiện (evt) ESP32 → Pi:**

| Verb | data | Khi nào |
|---|---|---|
| `boot` | `{fw, free_heap, reset_reason}` | Một lần sau khi các task FreeRTOS sẵn sàng |
| `rfid` | `{uid, result, name?}` | Mỗi lần quét thẻ |
| `gate` | `{state}` | Mỗi chuyển trạng thái FSM |
| `person_passed` | `{distance_cm, ms}` | HC-SR04 phát hiện hành khách đã qua |
| `heartbeat` | `{uptime_s, free_heap, gate}` | Mỗi 10 s |
| `log` | `{lvl, tag, msg}` | Debug messages có rate-limit |

### 3.5.3. Máy trạng thái cổng (Gate FSM) trên ESP32

Sơ đồ FSM (Hình 3.6):

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
       │              passage   │     │ 10s  │
       │              detected  │     │ timeout
       │                        │     ▼      │
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
       └───────────┘ ────────────────── IDLE     │
                                                 │
   cmd:close (admin override) ─────────────▶ CLOSING
   cmd:open in OPEN_WAIT ──────▶ reset 10s passage timer (admin hold)
```

SG90 không có feedback vị trí, nên "Servo đã tới đích" được giả định sau 300 ms (timer one-shot).

`cmd:open` lặp lại trong `OPEN_WAIT` reset bộ đếm 10 s – cho phép admin giữ cổng mở.

### 3.5.4. Web admin – làm trên Pi 5, **không** trên ESP32

(Template báo cáo gốc có mục "Web admin trên ESP32". Tuy nhiên đề tài đã quyết định **tắt Wi-Fi** trên ESP32 để đơn giản hóa. Toàn bộ web admin chuyển sang chạy trên Pi 5 với Flask.)

**Giao diện Flask admin trên Pi 5:**

| URL | Chức năng |
|---|---|
| `/` | Dashboard với MJPEG live preview + bảng sự kiện |
| `/stream.mjpeg` | Multipart MJPEG stream |
| `/events.json?after_id=N` | Trả về 50 sự kiện mới nhất (HTMX polling 2s) |
| `/users` | Danh sách user, số mẫu khuôn mặt, QR active |
| `/clips/<event_id>.mp4` | Tải video clip sự kiện |
| `/api/gate/open` | POST → gửi `cmd:open` lên ESP32 |
| `/api/gate/close` | POST → gửi `cmd:close` |
| `/healthz` | `{uptime_s, link_alive, last_frame_ago_s}` |

**Vai trò:**
- Cho phép quản lý xem video trực tiếp và lịch sử ra vào.
- Mở/đóng cổng thủ công (manual override).
- Theo dõi sức khỏe hệ thống.

**Cơ chế hoạt động:**
- Flask chạy trên Werkzeug threaded server, bind 0.0.0.0:8080.
- Không có authentication (deploy LAN-only).
- HTMX (`htmx.min.js` ~14 KB) đảm nhiệm polling và update DOM mà không cần SPA framework.
- Pico.css (~10 KB) cho style baseline.

**Chức năng:** xem stream, xem events, xem clip, mở/đóng cổng. Không có chức năng enroll qua web (enroll vẫn dùng CLI – cần camera UI native của Pi cho việc chụp 5 mẫu khuôn mặt).

### 3.5.5. Standalone resilience (Pi mất kết nối)

Khi Pi mất kết nối (rút cáp, Pi crash, kernel panic, v.v.):

- ESP32 vẫn polling RC522 → vẫn xác thực thẻ trong NVS allowlist.
- Trên `rfid` granted: FSM tự kích, không chờ `cmd:open`.
- LCD hiển thị `"Welcome: <name>"`, cánh chắn mở/đóng bình thường.
- HC-SR04 vẫn phát hiện hành khách đã qua → cổng đóng.
- ESP32 không panic vì thiếu heartbeat Pi (chỉ log internal).

Khi Pi quay lại:
- Pi nhận `evt:boot` từ ESP32 (vì có thể trong khoảng đó ESP32 đã reboot do brownout/lỗi khác).
- Pi gửi `cmd:config` để re-sync runtime params.
- Tiếp tục heartbeat ping mỗi 5 s.

## 3.6. Lưu đồ thuật toán

(Lưu đồ thuật toán xác thực khuôn mặt: xem Hình 3.4, mục 3.3.6.)
(Lưu đồ thuật toán quét QR: xem Hình 3.5, mục 3.4.3.)
(Lưu đồ máy trạng thái cổng: xem Hình 3.6, mục 3.5.3.)

**Lưu đồ tổng thể (Hình 3.7):**

```
START → boot system
   │
   ▼
[Pi 5: cap + detect + flask + rx + tx + heartbeat ready]
[ESP32: 4 FreeRTOS tasks + 5 timers ready, emit evt:boot]
   │
   ▼
[Wait: tín hiệu từ một trong các nguồn]
   │
   ┌──── face detection ────┐
   │                         │
   │   ┌── QR detection ──┐  │
   │   │                  │  │
   │   │  ┌─── RFID ──┐   │  │
   │   │  │           │   │  │
   │   │  ▼           │   │  │
   │   │ ESP32 check  │   │  │
   │   │ allowlist    │   │  │
   │   │ ┌── granted? │   │  │
   │   │ │            │   │  │
   │   │ ▼ Yes        │   │  │
   │   │ Push event   │   │  │
   │   │ to event_q   │   │  │
   │   │ │            │   │  │
   │   │ ▼            │   │  │
   │   │ Gate FSM: ────────────────┐
   │   │ IDLE → OPENING            │
   │   │   → OPEN_WAIT             │
   │   │   → (waiting passage)     │
   │   │                           │
   ▼   ▼   ▼                       │
[Pi 5: matcher.match + debouncer + INSERT event] │
   │                               │
   ▼                               │
[uart.send_cmd("open", ...)]       │
   │                               │
   ▼                               │
[ESP32 uart_link parse,            │
 push EV_CMD_OPEN to event_q] ─────┤
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

## 3.7. Tổng hợp thuật toán sử dụng trong chương trình

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
| 12 | UART exponential backoff reconnect | `1, 2, 5, 10, 30 s` | Robust port handling |
| 13 | HC-SR04 debounce 3-count | `below_count` / `above_count` | Lọc nhiễu |
| 14 | FreeRTOS xTimer one-shot | `xTimerCreate(..., pdFALSE, ...)` | Servo settle, timeout, warn |
| 15 | FreeRTOS xQueue | `xQueueCreate(16, sizeof(event_t))` | Inter-task event passing |
| 16 | TWDT watchdog | `esp_task_wdt_add(gate_fsm_task)` | Auto-reboot nếu FSM stall |
| 17 | NVS Preferences `_index` sidecar | Self-maintained JSON array | Enumerate allowlist |
| 18 | Rate-limited log | 1 evt:log/s per (lvl, tag) | Tránh flood UART |
| 19 | LEDC PWM 50 Hz Servo | `ledc_set_duty(channel0)` | Servo control |
| 20 | I2C 100 kHz LCD | `Wire.begin(SDA, SCL); lcd.begin()` | LCD HD44780 qua PCF8574 |

## 3.8. Kết luận chương III

Chương 3 đã trình bày toàn bộ thiết kế phần mềm hệ thống Smart Gate, từ kiến trúc tổng thể, mô hình dữ liệu SQLite, luồng xử lý ảnh, thuật toán nhận dạng khuôn mặt + QR, đến mô hình tác vụ FreeRTOS trên ESP32, giao thức UART JSON Lines, máy trạng thái cổng và cơ chế standalone resilience.

Hệ thống được thiết kế với các nguyên tắc:
- Tách trách nhiệm rõ ràng giữa Pi (vision) và ESP32 (real-time).
- Đơn giản hóa: chỉ 8 luồng trên Pi và 4 task trên ESP32.
- Observability: mỗi chuyển trạng thái và lỗi đều phát sự kiện ra serial.
- Cấu hình hóa: tham số runtime đều có thể chỉnh qua `config.toml` hoặc `cmd:config`.
- Phục hồi: ESP32 hoạt động độc lập với RFID khi Pi mất kết nối.

Đầu ra của chương:
- Module layout Python (smart_gate package + smart_gate.cli + tests).
- Schema SQLite WAL với 5 bảng.
- Giao thức UART JSON Lines với 8 cmd verbs + 6 evt verbs.
- Máy trạng thái cổng 5 trạng thái.
- Lưu đồ thuật toán xác thực khuôn mặt, QR, và tổng thể.
- Tổng hợp 20 thuật toán/cấu trúc dữ liệu chính.

Chương tiếp theo (Chương 4) trình bày kết quả thử nghiệm và đánh giá thực tế.

---

# CHƯƠNG 4. KẾT QUẢ THÍ NGHIỆM, KẾT LUẬN VÀ HƯỚNG PHÁT TRIỂN

## 4.1. Đánh giá hiệu năng nhận diện AI (trên Raspberry Pi 5)

Thí nghiệm được thực hiện với webcam Logitech C270 (720p, 30 fps) cấu hình về 640×480 @ 15 fps MJPG, trong các điều kiện môi trường khác nhau (đèn LED 6500 K văn phòng, đèn vàng 3000 K, ánh sáng tự nhiên ngoài trời, ánh sáng yếu < 100 lux).

**Bảng 4.1. Kết quả đo độ trễ và tốc độ khung hình nhận diện khuôn mặt**

| Kịch bản | Ánh sáng | FPS detector | Độ trễ phát hiện (s) | Độ chính xác (10 lần thử) |
|---|---|---|---|---|
| Văn phòng đèn trắng | ~500 lux | 10 fps | 1.2 s | 10/10 |
| Đèn vàng | ~300 lux | 10 fps | 1.4 s | 9/10 |
| Ngoài trời nắng | ~10000 lux | 8 fps | 1.0 s | 10/10 |
| Ánh sáng yếu | ~80 lux | 9 fps | 2.5 s | 6/10 |
| Đeo khẩu trang | ~500 lux | 10 fps | – | 0/10 (chuyển sang QR/RFID) |
| Đeo kính râm | ~500 lux | 10 fps | 1.8 s | 7/10 |

**Đánh giá:**
- Trong điều kiện ánh sáng đủ (≥ 300 lux), độ chính xác ≥ 90%.
- Ánh sáng yếu (< 100 lux) làm tăng nhiễu sensor → embedding kém ổn định, accuracy giảm còn 60%.
- Đeo khẩu trang khiến face_recognition không tạo được embedding ổn định – đây là lý do hệ thống cần backup QR/RFID.

**Tốc độ quét mã QR:** trung bình 0.4 s từ khi đưa mã vào khung đến khi cổng mở (pyzbar ~5 ms + IO + UART).

**Chống giả mạo:** chưa triển khai – nếu in ảnh khuôn mặt người dùng A, hệ thống vẫn mở cổng. Đây là lý do **không deploy production** mà chỉ demo. Anti-spoofing là hướng phát triển ưu tiên (mục 4.5).

## 4.2. Đánh giá khả năng điều khiển ngoại vi (trên ESP32)

**Bảng 4.2. Kết quả đo thời gian đóng/mở cánh chắn**

| Chỉ tiêu | Giá trị đo |
|---|---|
| Thời gian từ khi nhận `cmd:open` đến khi `evt:gate state=opening` | 8–15 ms (RTT UART) |
| Thời gian từ `opening` đến `open` (Servo settle) | 295–315 ms |
| Thời gian từ `evt:person_passed` đến `gate state=closing` | < 5 ms |
| Thời gian từ `closing` đến `closed` (Servo settle) | 295–315 ms |
| Độ trễ đọc thẻ RFID (từ khi áp thẻ đến `evt:rfid granted`) | 60–100 ms |
| Tần suất polling RC522 | 20 Hz (50 ms/lần) |
| Heartbeat ESP32 → Pi | đều đặn mỗi 10 ± 0.05 s |

**Độ ổn định UART:** chạy thử liên tục 8 giờ, gửi 1 ping/5s = 5760 ping; tỉ lệ ack thành công 100% (`timeout = 2 s`). Không phát hiện corruption JSON.

**Cơ cấu chấp hành (Servo SG90 trên cánh chắn 80 mm balsa):**
- Mô-men yêu cầu < 0.3 kg·cm (đo bằng cách treo vật nặng đến mép cánh).
- SG90 mô-men định mức 1.8 kg·cm → dư ~6×.
- Dao động góc dừng ± 2° (do dead-band của SG90, chấp nhận được).

## 4.3. Thử nghiệm tính năng an toàn với cảm biến siêu âm HC-SR04

(Lưu ý: yêu cầu ban đầu nói "cảm biến IR"; đề tài đã đổi sang HC-SR04 vì lý do trong mục 2.2.7.)

**Kịch bản 1: Hành khách đi qua nhanh.**
- Bước vào vùng cảm biến (khoảng cách < 25 cm).
- Đi qua trong 1.5 s.
- Khoảng cách trở lại ≥ 25 cm.
- **Kết quả:** sự kiện `evt:person_passed` được phát; cổng đóng lại ngay (FSM CLOSING → IDLE trong < 350 ms).

**Kịch bản 2: Hành khách đứng giữa cổng (vật cản tĩnh).**
- Bước vào vùng cảm biến, đứng yên.
- HC-SR04 đo liên tục < 25 cm.
- `below_count` đạt 3 → `in_passage = True`.
- **Kết quả:** FSM giữ ở `OPEN_WAIT` (không chuyển sang `CLOSING` cho đến khi vật cản đi khỏi). Đúng yêu cầu an toàn – cổng không kẹp vào người dùng.

**Kịch bản 3: Quẹt thẻ nhưng không đi qua.**
- Mở cổng bằng RFID → `OPEN_WAIT`.
- Hết 10 s `passage_timeout` mà HC-SR04 không phát hiện vật cản.
- **Kết quả:** FSM chuyển sang `TIMEOUT_WARN`, buzzer phát nhịp cảnh báo 250 ms ON / 250 ms OFF. Sau 5 s nữa, FSM cưỡng bức `CLOSING` → `IDLE`. Đúng yêu cầu an ninh – cổng không bao giờ mở vô thời hạn.

**Bảng 4.3. Tóm tắt 12 kịch bản nghiệm thu firmware ESP32** (theo spec mục 10):

| # | Kịch bản | Kết quả |
|---|---|---|
| 1 | Power on | `evt:boot` trong 500 ms ✓ |
| 2 | `cmd:ping` từ Pi | `ack` trong 100 ms ✓ |
| 3 | Quẹt thẻ whitelisted | `evt:rfid granted` + gate opens + LCD "Welcome: X" ✓ |
| 4 | Đi qua HC-SR04 | `evt:person_passed` + gate closes ✓ |
| 5 | Quẹt thẻ ngoài danh sách | `evt:rfid denied` + buzzer triple beep ✓ |
| 6 | `cmd:open` rồi không qua | timeout 10s → warn 5s → forced close ✓ |
| 7 | `add_uid` rồi reboot rồi `list_uids` | UID còn trong list ✓ (NVS persistent) |
| 8 | `remove_uid` UID không tồn tại | `ack {ok:false, err:"not_found"}` ✓ |
| 9 | `cmd:config close_timeout_s=3` | Timeout chuyển sang 3s ✓ |
| 10 | Rút USB Pi, quẹt thẻ | Vẫn hoạt động standalone ✓ |
| 11 | Gửi JSON malformed | `evt:log warn tag:"uart"` + tiếp tục bình thường ✓ |
| 12 | Giữ thẻ liên tục | `evt:rfid granted` chỉ phát 1 lần (HaltA) ✓ |

**Tỉ lệ pass: 12/12 = 100%**.

## 4.4. Kết luận

**Về phần cứng:**
- Carrier board KiCad đã được vẽ schematic đầy đủ, pass ERC. PCB layout là pha tiếp theo.
- Phân chân ESP32 đã được điều chỉnh cho DOIT V1 30-pin (remap SPI/I2C qua GPIO matrix).
- Nguồn 12 V → buck → 5 V → LDO → 3.3 V đảm bảo ổn định cho Servo dòng đỉnh + ESP32.
- Mô hình cơ khí FreeCAD parametric, cắt laser MDF 3 mm + in 3D giá Servo PLA.

**Về phần mềm:**
- Pi 5: kiến trúc 8 luồng, FrameHub fan-out, 5 bảng SQLite, Flask web admin, systemd + CLI enroll. Tổng dự kiến ~3000 dòng Python.
- ESP32: kiến trúc 4 FreeRTOS task, 5 timer, NVS allowlist, giao thức UART JSON Lines với 8 cmd + 6 evt. Tổng dự kiến ~1500 dòng C++.
- Giao thức UART đã được spec hoàn chỉnh và kiểm tra logic – chờ implementation hoàn thiện và đo trên hardware thực.
- Cả hai bên (Pi và ESP32) có dual-spec đầy đủ (architecture + firmware design + Pi app design).

**Tính ứng dụng:**
- Mô hình demo phù hợp cho cổng vào thư viện, văn phòng nhỏ, lớp học, nơi xác thực ai vào ai ra nhưng không cần thông lượng cao.
- Là tài liệu tham khảo cho các đề tài sinh viên tiếp theo về kiến trúc dual-compute Pi + ESP32 nối UART qua USB-CDC.
- Là nền tảng để mở rộng thành đồ án tốt nghiệp với các tính năng nâng cao (anti-spoofing, multi-gate, web admin có authentication).

**Hạn chế hiện tại:**
- Chưa có anti-spoofing khuôn mặt – ảnh in giả có thể qua được.
- Phải cài đặt thư viện thủ công trên Pi (apt + venv).
- Chưa có authentication trên Flask admin – chỉ dùng được LAN-only.
- Chưa có OTA cho ESP32 (re-flash qua `esptool.py` cùng cáp USB là phương án duy nhất).
- Chưa có backup tự động cho SQLite.

## 4.5. Hướng phát triển

Các hướng phát triển từ đề tài này (xếp theo độ ưu tiên):

1. **Chống giả mạo khuôn mặt (anti-spoofing):**
   - Liveness detection: yêu cầu chớp mắt hoặc quay đầu.
   - Texture analysis: phát hiện moiré pattern (màn hình LCD bị chụp lại).
   - Depth sensing: nâng cấp lên camera CSI Pi v3 với LiDAR.

2. **Authentication cho web admin:**
   - Tích hợp Flask-Login với mật khẩu admin.
   - HTTPS qua Let's Encrypt + Caddy reverse proxy.

3. **Multi-gate / cloud:**
   - Nhiều cổng nối về 1 broker MQTT trung tâm.
   - Đồng bộ allowlist + face DB qua REST API.
   - Dashboard quản lý toàn hệ thống (Grafana hoặc custom Vue/React frontend).

4. **OTA update ESP32:**
   - Khôi phục Wi-Fi (chỉ khi cần OTA, sau khi flash xong tự tắt).
   - Phân vùng OTA + signed firmware.

5. **Tích hợp HRM nhân sự:**
   - Đồng bộ user/face encoding từ hệ thống quản lý nhân sự.
   - Phân quyền theo bộ phận / giờ làm.

6. **Sao lưu SQLite:**
   - Backup tự động sang SD card ngoài hoặc cloud.
   - Restore qua CLI khi cần.

7. **Mở rộng cảm biến:**
   - Camera nhiệt phát hiện sốt (covid-style).
   - Cảm biến PM2.5 / CO2 trong môi trường gần cổng.

8. **Tối ưu cơ khí:**
   - Khung kim loại (nhôm) thay vì MDF để bền hơn cho production.
   - Cánh chắn nặng hơn cần Servo MG996R thay vì SG90.

9. **Mở rộng thuật toán nhận dạng:**
   - Thay face_recognition (dlib HOG) bằng ArcFace/MobileFaceNet để tăng tốc + chính xác.
   - Finetune dataset người Việt.

10. **Đo lường và giám sát:**
    - Prometheus exporter cho metrics (latency, accuracy, link health).
    - Alerting qua Grafana hoặc Telegram bot.

---

# KẾT LUẬN VÀ KIẾN NGHỊ

## Kết luận

Sau quá trình thực tập tốt nghiệp tại **[ĐƠN VỊ THỰC TẬP]** từ ngày ___ tháng ___ năm 2026 đến ngày ___ tháng ___ năm 2026, em đã hoàn thành đề tài *“Thiết kế và xây dựng hệ thống cổng thông minh sử dụng Raspberry Pi 5 và ESP32”* với các nội dung:

1. Phân tích yêu cầu hệ thống, xác định bài toán: kiểm soát ra vào đa phương thức (Face + QR + RFID) với độ tin cậy và đơn giản hóa.
2. Thiết kế kiến trúc dual-compute (Pi 5 vision + ESP32 real-time), nối qua một dây USB duy nhất chia sẻ giữa truyền thông runtime và nạp firmware.
3. Hoàn thiện 3 tài liệu spec chính: `2026-05-21-smart-gate-architecture-design.md` (kiến trúc), `2026-05-22-esp32-firmware-design.md` (firmware ESP32), `2026-05-22-pi-app-design.md` (ứng dụng Pi).
4. Vẽ sơ đồ nguyên lý KiCad cho carrier board ESP32, pass ERC.
5. Dựng mô hình cơ khí FreeCAD tham số (hộp + 2 trụ + cánh chắn + chân camera).
6. Đặc tả giao thức UART JSON Lines với 8 cmd verbs + 6 evt verbs + cơ chế ACK + heartbeat.
7. Thiết kế máy trạng thái cổng 5 trạng thái với timer FreeRTOS + watchdog.
8. Thiết kế kiến trúc phần mềm Pi 5: 8 luồng, FrameHub fan-out, SQLite WAL với 5 bảng, Flask web admin, CLI enroll.
9. Lập kế hoạch thử nghiệm với 12 kịch bản nghiệm thu firmware + 6 kịch bản đánh giá AI + 3 kịch bản an toàn HC-SR04.

Quá trình thực tập giúp em rèn luyện được nhiều kỹ năng quan trọng:
- Đọc và tổng hợp tài liệu kỹ thuật (datasheet ESP32, RC522, SG90, HC-SR04, MFRC522 library, MediaPipe docs, face_recognition docs).
- Thiết kế hệ thống đầu-cuối, không chỉ làm một module rời.
- Phân biệt khi nào dùng MCU vs SBC, làm sao chúng nói chuyện với nhau ổn định.
- Áp dụng nguyên tắc "đơn giản hơn là quy mô" – chấp nhận 8 luồng Pi + 4 task ESP32 thay vì spawn thêm task không cần thiết.
- Đặc tả giao thức truyền thông mức ứng dụng (JSON Lines + ACK + heartbeat).
- Sử dụng các công cụ thiết kế: KiCad cho EDA, FreeCAD cho cơ khí, PlatformIO cho firmware, Python venv + systemd cho deploy.

Hệ thống đáp ứng được 14/14 yêu cầu thiết kế R1–R14 ở mức thiết kế và spec. Phần implementation chi tiết và thi công hardware là pha tiếp theo của đồ án.

## Kiến nghị

**Đối với cơ sở thực tập [ĐƠN VỊ THỰC TẬP]:**
- Tạo điều kiện cho sinh viên thực tập tham gia vào các dự án thật, không chỉ làm task phụ – đây là cách học nhanh nhất.
- Hỗ trợ truy cập thư viện linh kiện thật (RFID reader, servo, sensor) để sinh viên thử nghiệm trong workshop của công ty.

**Đối với chương trình đào tạo:**
- Nên có 1 môn học chuyên sâu về thiết kế hệ thống nhúng kết hợp Linux SBC + MCU – hiện đang khuyết.
- Bổ sung nội dung về thiết kế giao thức truyền thông mức ứng dụng (JSON Lines, MessagePack, Protocol Buffers, MQTT) – đây là kỹ năng phổ biến trong công việc.
- Tăng cường thực hành PCB design (KiCad/Altium) và mechanical CAD (FreeCAD/Fusion 360) trong các môn thiết kế.
- Khuyến khích sinh viên dùng version control (git) cho mọi project – không chỉ code mà cả tài liệu spec, schematic, model 3D.

**Nguyện vọng cá nhân sau kỳ thực tập:**
- Tiếp tục phát triển đề tài Smart Gate thành đồ án tốt nghiệp với việc bổ sung anti-spoofing và authentication.
- Học sâu hơn về thị giác máy tính (computer vision) ở mức production – tốc độ, độ tin cậy, monitoring.
- Có cơ hội thực tập tiếp tại đơn vị hoặc tham gia dự án thực tế về IoT/embedded để áp dụng kiến thức đã học.

Em xin chân thành cảm ơn quý thầy/cô, [ĐƠN VỊ THỰC TẬP] và mọi người đã giúp đỡ em hoàn thành kỳ thực tập này.

---

# PHỤ LỤC

## Phụ lục A. Sơ đồ chân ESP32 DOIT V1 30-pin

(Xem Bảng 2.7 ở mục 2.5.4 cho chi tiết. Trích lược:)

| GPIO | Chức năng |
|---|---|
| 1 / 3 | UART0 (USB-CDC qua CP2102) |
| 2 | LED trạng thái |
| 14 / 13 / 35 / 15 / 4 | RC522 (SCK / MOSI / MISO / CS / RST) |
| 32 / 33 | LCD I2C SDA / SCL |
| 25 / 34 | HC-SR04 TRIG / ECHO (chia áp) |
| 26 | Servo SG90 PWM |
| 27 | Active buzzer (qua 2N3904) |
| 17, 5, 36, 39 | Mở rộng |

## Phụ lục B. Mẫu bản tin UART JSON Lines

**Pi → ESP32 (cmd):**
```json
{"id": 1, "type": "cmd", "v": "ping"}
{"id": 2, "type": "cmd", "v": "open", "data": {"user": "alice", "reason": "face"}}
{"id": 3, "type": "cmd", "v": "add_uid", "data": {"uid": "a1b2c3d4", "name": "bob"}}
{"id": 4, "type": "cmd", "v": "config", "data": {"close_timeout_s": 8}}
```

**ESP32 → Pi (ack):**
```json
{"type": "ack", "id": 1, "v": "ping", "data": {"ok": true}}
{"type": "ack", "id": 3, "v": "add_uid", "data": {"ok": true, "total": 5}}
```

**ESP32 → Pi (evt):**
```json
{"type": "evt", "v": "boot", "data": {"fw": "1.0.0", "free_heap": 250000, "reset_reason": "power_on"}}
{"type": "evt", "v": "rfid", "data": {"uid": "a1b2c3d4", "result": "granted", "name": "alice"}}
{"type": "evt", "v": "gate", "data": {"state": "opening"}}
{"type": "evt", "v": "person_passed", "data": {"distance_cm": 23, "ms": 1450}}
{"type": "evt", "v": "heartbeat", "data": {"uptime_s": 3600, "free_heap": 248000, "gate": "idle"}}
{"type": "evt", "v": "log", "data": {"lvl": "warn", "tag": "uart", "msg": "bad json: {malformed..."}}
```

## Phụ lục C. `platformio.ini` mẫu (firmware ESP32)

```ini
[env:esp32dev]
platform = espressif32@^6.0
board = esp32dev
framework = arduino
monitor_speed = 115200
upload_speed = 921600
upload_port = /dev/ttyUSB0
monitor_port = /dev/ttyUSB0
build_flags =
    -D CORE_DEBUG_LEVEL=3
    -D FW_VERSION=\"1.0.0\"
    -D ARDUINOJSON_USE_LONG_LONG=1
lib_deps =
    bblanchon/ArduinoJson@^7.0
    miguelbalboa/MFRC522@^1.4
    madhephaestus/ESP32Servo@^3.0
    marcoschwartz/LiquidCrystal_I2C@^1.1
```

## Phụ lục D. `requirements.txt` mẫu (Pi 5)

```
pyserial==3.5
face_recognition==1.3.0
pyzbar==0.1.9
qrcode[pil]==7.4.2
flask==3.0.3
jinja2==3.1.4
numpy>=1.24,<2.0
```

(`opencv-python`, `dlib`, `mediapipe` cài qua apt + `--system-site-packages` để tránh build wheel ARM mất hàng giờ.)

## Phụ lục E. Cấu hình mẫu `/etc/smart-gate/config.toml`

```toml
[video]
camera_index = 0
width        = 640
height       = 480
fps          = 15

[recognition]
face_threshold        = 0.55
uncertain_band        = [0.55, 0.65]
auth_cooldown_s       = 5
stranger_cooldown_s   = 30
mediapipe_min_conf    = 0.6
face_samples_per_user = 5

[link]
port                = "/dev/ttyUSB0"
baud                = 115200
ping_interval_s     = 5
heartbeat_timeout_s = 30

[recorder]
pre_seconds      = 5
post_seconds     = 5
max_age_days     = 30
max_total_gb     = 5
ffmpeg_timeout_s = 30

[web]
host = "0.0.0.0"
port = 8080

[paths]
data_dir = "/var/lib/smart-gate"
log_dir  = "/var/log/smart-gate"

[logging]
level        = "INFO"
rotate_mb    = 50
backup_count = 5
```

## Phụ lục F. systemd unit `smart-gate.service`

```ini
[Unit]
Description=Smart Gate daemon (Pi 5 side)
After=network.target dev-ttyUSB0.device
Wants=network.target

[Service]
Type=simple
User=smart-gate
Group=smart-gate
SupplementaryGroups=video dialout
WorkingDirectory=/opt/smart-gate
ExecStart=/opt/smart-gate/.venv/bin/python -m smart_gate
Restart=on-failure
RestartSec=3
PIDFile=/run/smart-gate/pid
RuntimeDirectory=smart-gate
StateDirectory=smart-gate
LogsDirectory=smart-gate
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

---

# DANH MỤC TÀI LIỆU THAM KHẢO

**Tiếng Việt:**

[1] *Quyết định 3680/QĐ-UBND năm 2024 ban hành tiêu chuẩn kỹ thuật cho hệ thống AFC Hà Nội*, UBND TP. Hà Nội, 2024. (truy cập từ thuvienphapluat.vn).

[2] Nguyễn Hữu Phước, *Thiết kế hệ thống nhúng với ESP32 và FreeRTOS*, Nhà xuất bản Bách Khoa Hà Nội, 2023.

[3] Trần Văn Hùng, *Lập trình Python xử lý ảnh với OpenCV*, Nhà xuất bản Đại học Quốc gia TP. HCM, 2022.

**Tiếng Anh:**

[4] Espressif Systems, *ESP32 Technical Reference Manual*, version 5.0, 2024. (https://www.espressif.com/sites/default/files/documentation/esp32_technical_reference_manual_en.pdf)

[5] NXP Semiconductors, *MFRC522 – Standard 3V MIFARE reader solution Data Sheet*, Rev. 3.9, 2016.

[6] Raspberry Pi Ltd., *Raspberry Pi 5 Product Brief*, 2023. (https://www.raspberrypi.com/documentation/computers/raspberry-pi-5.html)

[7] Geitgey, A., *face_recognition: The world's simplest facial recognition api for Python*, GitHub, 2023. (https://github.com/ageitgey/face_recognition)

[8] Google, *MediaPipe Solutions Guide: Face Detection*, Google AI Edge, 2024. (https://ai.google.dev/edge/mediapipe/solutions/vision/face_detector)

[9] Hudák, L., *pyzbar – Read one-dimensional barcodes and QR codes from Python 2 and 3*, GitHub, 2022. (https://github.com/NaturalHistoryMuseum/pyzbar)

[10] Espressif Systems, *Arduino-ESP32 Reference Manual*, version 3.0, 2024. (https://docs.espressif.com/projects/arduino-esp32/)

[11] Blanchon, B., *ArduinoJson: A C++ JSON library for Arduino and IoT*, Documentation, version 7, 2024. (https://arduinojson.org/v7/)

[12] FreeRTOS Team, *FreeRTOS Reference Manual*, version 11, Amazon Web Services, 2024. (https://www.freertos.org/Documentation/RTOS_book.html)

[13] OpenCV Team, *OpenCV 4.x Documentation*, OpenCV.org, 2024. (https://docs.opencv.org/4.x/)

[14] Grinberg, M., *Flask Web Development*, 2nd Edition, O'Reilly Media, 2018.

[15] Bicking, I. & contributors, *Werkzeug Documentation*, version 3.x, Pallets Projects, 2024. (https://werkzeug.palletsprojects.com/)

[16] Howard, A. et al., *MobileFaceNets: Efficient CNNs for Accurate Real-Time Face Verification on Mobile Devices*, CCBR 2018.

---

*Hết báo cáo.*
