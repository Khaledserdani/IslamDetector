# تنفيذ جسر UART على ESP32-S3 — Rev A

**الحالة:** مكوّن ESP-IDF أضيف إلى المشروع؛ البناء الآلي مطلوب لإثبات توافقه. لا يوجد توصيل عتادي أو اختبار UART loopback بعد.

## ما أضيف
- مشروع ESP-IDF مستقل داخل firmware/esp32_s3_bridge.
- المكوّن rev_a_uart_bridge يستخدم UART driver الرسمي وFreeRTOS event queue وRX ring buffer.
- Task استقبال يقرأ البيانات على دفعات ثم يغذي parser بايتاً بايتاً، حتى يكتشف CRC/header failure قبل معالجة البايت التالي.
- تمر DEVICE_INFO وMEASUREMENT إلى rev_a_session_accept_frame(). لا تدخل MEASUREMENT إلى queue إلا بعد DEVICE_INFO صحيح.
- queue القياسات تحفظ raw16 وصيغة ADC والدقة وVREF وmetadata generation والقيم المفسرة للنوافذ الصالحة.
- إرسال HELLO وGET_INFO عند البدء، ثم إعادة GET_INFO كل ثانية حتى وصول DEVICE_INFO صالح.
- عند FIFO overflow أو ring-buffer full أو framing/parity/break error: تفريغ RX وإعادة parser وإبطال DEVICE_INFO ثم طلبه مجدداً.
- queue القياسات محدودة؛ عند امتلائها تسقط العينة الجديدة وتزيد dropped_measurements بدلاً من حجب UART task.
- API لإرسال أوامر البروتوكول وقراءة الحالة واستلام القياسات.

## إعداد الأرجل
لا يوجد رقم GPIO مثبت في المصدر. الجسر معطل افتراضياً، وTX/RX=-1، وUART1 هو الافتراضي مع إبقاء UART0 للـconsole.
بعد مطابقة رقم لوحة ESP32-S3 ومخططها الفعلي فقط:
1. شغّل idf.py set-target esp32s3.
2. شغّل idf.py menuconfig.
3. فعّل الجسر واختر UART1 أو UART2 وأدخل TX/RX GPIO الصحيحين.
4. لا تفعّل الجسر إذا بقي GPIO على -1؛ المشروع يرفض البناء.
5. شغّل idf.py build.
التوصيل المنطقي لاحقاً: ESP32 TX إلى RP2040 RX والعكس، مع GND مشترك ومنطق 3.3V فقط. لا 5V إلى GPIO. لا تختَر GPIO بالتخمين.

## إعداد النقل
UART1 افتراضياً؛ UART2 متاح؛ 921600 baud و8N1؛ RX buffer 4096؛ TX buffer 512؛ event queue 16؛ measurement queue 8؛ قراءة chunks من 128 byte؛ GET_INFO retry كل 1000ms.
هذه إعدادات Firmware وليست قياساً لمعدل نقل فعلي أو ضماناً لعدم فقد البيانات. يلزم قياس throughput تحت حمل Wi-Fi لاحقاً.

## الحدود
- لا يوجد ACK decoder أو RP2040 command receiver/DEVICE_INFO transmitter بعد.
- لا يوجد Wi-Fi/WebServer/JSON endpoint أو ربط Android.
- لا يوجد UART loopback أو قياس فعلي بين اللوحتين.
- لا يوجد TX power أو MOSFET أو ملف بحث ضمن هذا البرنامج.

## بوابة القبول التالية
1. نجاح ESP-IDF build في CI.
2. تثبيت GPIO بعد مراجعة مخطط لوحة التطوير.
3. UART loopback منخفض الجهد ثم ربط اللوحتين بمنطق 3.3V.
4. إثبات HELLO/GET_INFO/DEVICE_INFO وقياس throughput والفقد.
5. إضافة RP2040 ACK/command receiver وDEVICE_INFO transmitter.
6. بعد ذلك ربط القياسات بخادم Wi-Fi.


## نتيجة البناء الآلي

اكتمل CI #1315 على commit f3d2516 بنجاح في الوظائف الأربع. ESP-IDF release-v5.4 ترجم rev_a_uart_bridge وrev_a_protocol وapp_main وربط مشروع ESP32-S3 وأنتج BIN. هذا يثبت compile/link فقط، وليس flashing أو تشغيل UART على لوحة فعلية.

بعد هذا التشغيل عولجت ملكية retry state ووقف FreeRTOS task في commits 621e283 وa39fbaa. تحقق الكود الأحدث جارٍ في CI #1318؛ لا تسجل هذه التعديلات نجاحاً حتى تنتهي الوظائف الأربع.
