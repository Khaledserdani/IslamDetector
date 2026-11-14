# وحدة الاتصال وتحديث Firmware من الهاتف — ISLAM NEXTGEN

التاريخ: 2026-11-14
الفرع: hardware/islam-nextgen-final-platform
الحالة: معمارية محددة ومرشح شراء محلي؛ لا شراء قبل اكتمال BOM.

## 1. تقسيم المعالجات

- **STM32G474RE / NUCLEO-G474RE:** مسؤول عن TX timing، HRTIM، current trip، AFE recovery، ADC1/ADC2، DMA، ومعالجة الإشارة الحرجة. لا ينفذ Wi-Fi ولا يعتمد على الهاتف في التوقيت.
- **ESP32-S3 N16R8 DevKitC-1:** مسؤول عن Wi-Fi AP، WebServer، نقل الإعدادات والبيانات، واجهة التطبيق، تخزين ملفات firmware مؤقتاً، وجسر تحديث STM32 عبر UART.
- **Android ISLAM DETECTOR:** واجهة المستخدم والتحكم والتسجيل. يتصل بـESP32-S3 عبر Wi-Fi، ولا يرسل نبضات زمنية مباشرة إلى STM32.

هذا فصل متعمد: لا نستخدم ADC الداخلي لـESP32-S3 كمسار قياس PI، ولا نحمل Wi-Fi مهام timing الحساسة.

## 2. لوحة Wi-Fi المحددة

**ESP32-S3 N16R8 DevKitC-1**، غير نسخة الكاميرا:
- ESP32-S3-WROOM-1، Flash 16MB، PSRAM 8MB.
- Wi-Fi 2.4GHz وBluetooth LE.
- USB-C مزدوج، CP2102 USB-UART، 45 GPIO.
- BinaryTech يعرض نسخة N16R8 بسعر2400 دج ومخزون ظاهر، لكن رؤوسها غير ملحومة.
- TIKNO يعرض N16R8 بسعر2500 دج، مع خيار لحام الرؤوس مسبقاً +300 دج؛ هذا الخيار يطابق شرط عدم طلب لحام يدوي.

مصادر التوريد:
https://tikno.edutech.dz/products/esp32-s3-n16r8-dual-core-ai-devkit-type-c
https://binarytech-dz.com/product/po46647335
https://powerlab.dz/product/esp32-s3-devkitm/

**اختيار التوريد المفضل:** TIKNO مع خيار pre-soldered headers؛ السعر الظاهر الإجمالي 2800 دج قبل أي شحن. يلزم تأكيد المخزون والخيار عند الطلب.

## 3. الربط بين ESP32-S3 وSTM32G474

USART3 على STM32G474:
- PB10 = USART3_TX على CN9 pin 7 (D6).
- PB11 = USART3_RX على CN10 pin 17.
- UART TTL 3.3V؛ الربط متقاطع TX↔RX مع GND مشترك.
- مقاومات سلسلة صغيرة وحماية ESD عند الكابل.
- سرعة تشغيل التطبيق يمكن أن تكون 460800 أو921600 بعد اختبار سلامة الرابط؛ لا نعتمدها قبل التحقق.

مرشح GPIO على ESP32-S3:
- GPIO17 = UART1_TX نحو PB11 (STM32 RX).
- GPIO18 = UART1_RX من PB10 (STM32 TX).
- GPIO16 = خط تحكم احتياطي لمدخل PB8/BOOT0، لكنه لا يفعّل ROM bootloader افتراضياً قبل ضبط option bytes.
- GPIO15 = تحكم NRST عبر ترانزستور open-drain.

يجب تدقيق pinout النهائي للوحة ESP32-S3 المختارة، وعدم استخدام GPIO0/3/45/46 كأرجل تحكم بسبب أدوار strapping.

## 4. تحديث STM32 من الهاتف دون كمبيوتر

وثيقة ST AN2606 تؤكد أن STM32G47xxx/G48xxx يدعم ROM system bootloader عبر USART1/2/3، وUSART3 متاح على PB10/PB11.

التسلسل:
1. يرفع تطبيق Android ملف Firmware إلى ESP32-S3 عبر Wi-Fi.
2. ESP32 يتحقق من الحجم وSHA-256 ونسخة الملف ويخزنه مؤقتاً.
3. يطلب من STM32 الدخول في وضع التحديث.
4. ESP32 يرفع BOOT0 (PB8) ثم يعمل reset عبر NRST.
5. STM32 يدخل ROM bootloader.
6. ESP32 يرسل بروتوكول ST USART bootloader على USART3 PB10/PB11 (8-bit, even parity, 1 stop bit).
7. بعد كتابة الفلاش والتحقق من checksum، يعيد ESP32 التشغيل مع BOOT0 منخفض.
8. STM32 يقلع من التطبيق الجديد ويرسل version/health handshake.
9. إذا فشل التحقق، لا يُعلن التحديث ناجحاً؛ يحتفظ ESP32 بالملف السابق ويعيد المحاولة/يطلب recovery.

المصدر الرسمي:
https://www.st.com/resource/en/application_note/an2606-introduction-to-stm32-microcontroller-system-memory-boot-mode-stmicroelectronics.pdf

ملاحظة: هذا التحديث يستخدم ROM bootloader الرسمي؛ لا نعتمد على Android لتشغيل ST-LINK أو SWD. يجب تنفيذ توصيل BOOT0/NRST بترانزستورات وحماية مناسبة، وتأكيد أن نسخة NUCLEO-G474RE المختارة تتيح الوصول إلى PB8/NRST عبر موصلاتها.

## 5. الأثر على المنافذ والطاقة

- PB10/PB11 محجوزان حصرياً للربط UART بين المعالجين؛ PB10 على CN9 pin 7 وPB11 على CN10 pin 17.
- PB8 محجوز كخيار BOOT0 على CN7 pin 7؛ لا نستخدمه I2C1 في التصميم الأساسي. يجب ضبط option bytes لأن BOOT0 غير موصول افتراضياً إلى دائرة اختيار boot.
- 5V من Power Bank يغذي Nucleo وESP32-S3 عبر توزيع طاقة محمي، مع 3.3V مستقلة/مفلترة للـAFE.
- 12V بطارية مستقلة لمسار TX؛ لا تُغذى قدرة TX من Power Bank.
- لا بد من أرضي مشترك منظم ومسارات منفصلة لعودة تيار TX عن AFE وWi-Fi.

## 6. حالة الاعتماد

- **معتمد معمارياً:** STM32G474 للقياس/التوقيت + ESP32-S3 N16R8 للاتصال والتحديث + Android للواجهة.
- **مرشح شراء محلي:** ESP32-S3 N16R8 مع headers ملحومة مسبقاً من TIKNO.
- **مرشح شراء غير محلي مؤكد:** NUCLEO-G474RE؛ لا يوجد مخزون جزائري مؤكد حتى الآن.
- **غير معتمد بعد:** كابل/موصل UART النهائي، GPIOs النهائية بعد مراجعة لوحة DevKit المختارة، دائرة BOOT0/NRST، توزيع 5V، وبروتوكول التحديث.


## 7. تدقيق GPIO لوحة ESP32-S3 DevKitC-1 N16R8

دليل Espressif الرسمي للوحة DevKitC-1 v1.0 يطابق التوزيع التالي:
- GPIO17 = U1TXD.
- GPIO18 = U1RXD.
- GPIO15 وGPIO16 أرجل XTAL 32kHz اختيارية، لكنها متاحة كـGPIO إذا لم تُركب crystal 32kHz.
- نتجنب GPIO0 وGPIO3 وGPIO45 وGPIO46 لأنها strapping pins.
- GPIO35/36/37 غير متاحة في N16R8 لأنها مرتبطة بذاكرة Octal PSRAM.
- GPIO43/44 محجوزتان لـUART0/USB-to-UART bridge.

إذن GPIO17/18 للرابط التسلسلي وGPIO15/16 لخطوط boot/reset مقبولة مبدئياً، بعد التأكد من مراجعة PCB الفعلية للوحة التي يرسلها المورد.

المصدر الرسمي:
https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32s3/esp32-s3-devkitc-1/user_guide_v1.0.html


## 8. تصحيح التوصيلات الفعلية وفق UM2505 Rev.7

- STM32 PB10 / USART3_TX: **CN9 pin 7 (D6)**.
- STM32 PB11 / USART3_RX: **CN10 pin 17**.
- STM32 PB8 / BOOT0: **CN7 pin 7** (وموضع D15 على CN5 pin 10).
- STM32 NRST: **CN6 pin 14**.
- PB8/BOOT0 لا يختار ROM bootloader بمجرد توصيله؛ يوضح UM2505 أن BOOT0 غير موصول افتراضياً وأن option bytes تتحكم بالوظيفة. لذلك تحديث الهاتف يعتمد أساساً على jump-to-system-memory من Firmware سليم، بينما recovery الكامل بعد تلف Firmware يحتاج ST-LINK/مسار صيانة موثق، إلا إذا تم تهيئة option bytes ومسار JP7 بشكل صحيح.

تم إلغاء أي رقم موصل سابق يخالف هذه الخريطة.
