# تنفيذ جسر UART على ESP32-S3 — Rev A

**الحالة (2026-11-15):** مكوّن ESP-IDF وparser/session وUART task ومقابل RP2040 command responder/ACK/DEVICE_INFO منفذة برمجياً، واكتمل build على CI #1371 و#1372. لا يوجد توصيل عتادي أو UART loopback، وDEVICE_INFO يعلن ADC_NONE لأن ADC غير مركب.

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

## الحدود الحالية
- ACK decoder وRP2040 command receiver وDEVICE_INFO transmitter أصبحت منفذة برمجياً؛ لا يعني ذلك أن الاتصال اختبر على اللوحتين.
- لا يوجد UART loopback أو قياس فعلي بين ESP32-S3 وRP2040.
- لا يوجد Wi-Fi AP أو WebServer أو JSON endpoint أو ربط Android end-to-end.
- لا يوجد ADC مركب أو MEASUREMENT producer فعلي؛ DEVICE_INFO يعلن ADC_NONE.
- لا توجد مرحلة TX أو MOSFET أو ملف بحث أو interlock ضمن هذا البرنامج.

## بوابة القبول التالية
1. تحديد طراز ومراجعة مخطط كل لوحة، ثم قياس continuity للأرجل المختارة وهي مفصولة عن التغذية.
2. تنفيذ UART loopback منخفض الجهد وفق الإجراء في `REV_A_BENCH_TEST_PLAN_AR.md`: TX/RX متقاطعتان، GND مشترك، منطق3.3V فقط، دون ربط VCC بين اللوحتين.
3. إثبات HELLO ثم GET_INFO؛ المتوقع ACK صالح وDEVICE_INFO يعلن ADC_NONE، مع CRC صحيح وعدم وجود framing/overflow errors.
4. بعد تركيب ADS8861 والحماية والمرجع فعلياً، تفعيل PIO capture في نسخة اختبار منفصلة وقياس CONVST/SCLK/DOUT والنوافذ قبل قبول أي timing.
5. إضافة MEASUREMENT producer فقط بعد ADC metadata صحيحة وقراءات raw متحققة؛ ثم ربط queue بخادم Wi-Fi وJSON API.
6. تبقى START مرفوضة ولا توصل GP4 إلى MOSFET/ملف حتى اكتمال حساب الطاقة والارتداد والحماية وقفل الأمان.


## نتيجة البناء الآلي

اكتمل CI #1315 على commit f3d2516 بنجاح في الوظائف الأربع. ESP-IDF release-v5.4 ترجم rev_a_uart_bridge وrev_a_protocol وapp_main وربط مشروع ESP32-S3 وأنتج BIN. هذا يثبت compile/link فقط، وليس flashing أو تشغيل UART على لوحة فعلية.

بعد هذا التشغيل عولجت ملكية retry state ووقف FreeRTOS task في commits 621e283 وa39fbaa. تحقق الكود الأحدث جارٍ في CI #1318؛ لا تسجل هذه التعديلات نجاحاً حتى تنتهي الوظائف الأربع.


## تحقق محدث — 2026-11-14

- CI #1319 / run ID `43604013988` اكتمل Success في الوظائف الأربع: `protocol-tests` و`android-app` و`rp2040-firmware` و`esp32-s3-bridge`.
- سجل ESP-IDF يؤكد إنشاء صورة ESP32-S3 واكتمال Project build. هذا يثبت compile/link فقط؛ لم يحدث flash أو تشغيل على لوحة.
- تعديلا ملكية GET_INFO retry وإيقاف FreeRTOS task في commits `621e283` و`a39fbaa` دخلا في البناء الناجح #1319.
- الإعدادات لا تزال آمنة افتراضياً: `CONFIG_REV_A_UART_ENABLE=n)، وTX/RX GPIO=-1، وUART1 افتراضي وUART0 محفوظ للـconsole.
- CI #1320 على commit `61ab603`: عند آخر تحقق نجح protocol-tests (45 اختبار Python + C strict compile) وAndroid build/verify/upload؛ كان RP2040 وESP-IDF قيد التنفيذ. لا يعتمد هذا كنجاح كامل قبل اكتمال الوظيفتين.
- RP2040 لا يرسل DEVICE_INFO بعد؛ لذلك GET_INFO من ESP32 لا يحقق handshake حالياً. لا يوجد ACK decoder أو command receiver حتى الآن.
- لا تُفعّل UART حتى تثبيت أرقام الأرجل من مخطط اللوحة الفعلية. لا يوجد UART loopback أو اختبار throughput/fault recovery على العتاد.


## نتيجة CI النهائية — 2026-11-14

اكتمل CI #1320 / run ID `43607459283` على commit `61ab603` بنجاح في الوظائف الأربع:
- `esp32-s3-bridge`: ESP-IDF release-v5.4 compile/link Success.
- `rp2040-firmware`: build + `verify_uf2.py` + upload Success.
- `protocol-tests`: 45 اختبار Python وC strict compile/test Success.
- `android-app`: Gradle build + APK ZIP verification + upload Success.

هذا يثبت البناء الآلي فقط. يبقى الجسر معطلاً افتراضياً، وTX/RX GPIO=-1. لا يوجد RP2040 command receiver أو DEVICE_INFO transmitter أو ACK decoder، ولا يوجد UART loopback أو Flash أو اختبار Wi-Fi/Android end-to-end.



## تحديث 2026-11-15 — اكتمال الطرف البرمجي الأولي
- أضيف ACK v0.1 payload من3 بايتات (COMMAND_TYPE/STATUS/REASON) إلى parser المشترك، مع رفض تراكيب status/reason غير المتسقة.
- يقبل ESP32 ACK ويسجله في rev_a_uart_bridge_status_t بدلاً من اعتباره إطاراً مجهولاً يؤدي إلى إبطال DEVICE_INFO.
- RP2040 يستقبل HELLO/GET_INFO/START/STOP/SET_PROFILE/SELF_TEST على UART0؛ يرسل ACK، وGET_INFO يعيد DEVICE_INFO.
- ADC_NONE يمنع ادعاء أن ADS8861 مركب؛ أي MEASUREMENT قبل تركيب ADC يرفضه session gate.
- START يظل مرفوضاً لأن هذا firmware لا يملك TX stage أو interlock؛ لا يوصل GP4 إلى MOSFET أو ملف.
- الأرجل GP0/GP1 إعداد أولي فقط؛ يلزم مراجعة مخطط اللوحة الفعلية وUART loopback منخفض الجهد قبل اعتمادها.


## تحديث التحقق — CI #1371 (2026-11-15)
- HEAD `e37fde414924eed0344285e642b43982158f52eb` اجتاز الوظائف الأربع: `protocol-tests` و`esp32-s3-bridge` و`android-app` و`rp2040-firmware`.
- وظيفة البروتوكول شغلت 50 اختبار Python ثم C parser/session مع تحذيرات صارمة؛ كلاهما Success.
- RP2040 firmware يستقبل أوامر التحكم ويرسل ACK/DEVICE_INFO في منطق البرنامج؛ DEVICE_INFO يعلن ADC_NONE. لا يوجد قياس فعلي ولا UART loopback.
- ESP32-S3 UART task وparser/session compile/link ناجحان في ESP-IDF release-v5.4. إعداد Kconfig ما زال disabled وGPIO=-1؛ لا يتم تفعيل UART على لوحة غير محددة.
- RP2040 UF2 artifact ID `14166064302` اجتاز فحص 155 كتلة وFamily ID `0xE48BFF56`. هذا اختبار GP4/GP5/GP6 المنطقي؛ ADC capture driver مضمّن في البناء لكنه disabled افتراضياً.
- لا يوجد Wi-Fi/WebServer أو JSON API؛ تطبيق Android ينتظر `GET /status` و`POST /control`. الخطوة التالية UART loopback آمن ثم Wi-Fi API بعد اعتماد pinout.


## معالجة DEVICE_INFO غير الصالح — 2026-11-16

- إذا كان إطار DEVICE_INFO سليماً من ناحية SYNC/length/CRC لكنه يحمل ADC metadata غير متوافقة، ترفضه طبقة session وتبطل metadata السابقة.
- يزامن جسر ESP32 الآن حالة status العامة مع الإبطال، ويمسح نسخة ADC القديمة من الحالة المنشورة، ويصفّر مهلة الطلب لإعادة GET_INFO فوراً.
- يمنع ذلك ظهور `device_info_valid=true` أو هوية ADC قديمة في status بعد أن تكون طبقة session قد أغلقت بوابة القياس.
- هذا إصلاح برمجي محافظ؛ يلزم CI جديد ثم اختبار fault-injection/loopback فعلي لاحقاً. لا يثبت اتصال UART على اللوحات.
