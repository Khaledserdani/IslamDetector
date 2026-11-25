# ESP32-S3 Rev A — UART bridge

**الحالة عند 2026-11-15:** تنفيذ برمجي أولي مكتمل البناء على CI #1371؛ لا يوجد بعد اتصال فعلي بين اللوحتين، ولا Wi-Fi/WebServer، ولا Flash على لوحة ESP32-S3.

## مكونات البرنامج

### محلل البروتوكول والجلسة
- `components/rev_a_protocol` محلل C11 محمول، يتحقق من SYNC/version/length/CRC16 ويستعيد التزامن بعد الضجيج أو الإطار التالف.
- يدعم ACK وDEVICE_INFO وMEASUREMENT، مع فحص ADC metadata وsample count وVALID_MASK وSweep flags.
- يحافظ على raw16؛ لا يفسر الكلمات إلا بعد DEVICE_INFO مطابق. ADS8861 = signed 16-bit two's-complement، وADS7054 = signed 14-bit two's-complement.
- `rev_a_session` يمنع قبول MEASUREMENT قبل DEVICE_INFO، ويرفض القياسات عند ADC_NONE، ويأخذ metadata snapshot لكل سجل.
- encoder الأوامر يرسل HELLO وGET_INFO وSTART وSTOP وSET_PROFILE وSELF_TEST. ACK v0.1 payload ثابت من 3 bytes: COMMAND_TYPE/STATUS/REASON.

### UART task على ESP32-S3
- `rev_a_uart_bridge` يستخدم ESP-IDF UART driver وRX ring buffer وevent queue وFreeRTOS task.
- عند البدء يرسل HELLO ثم يكرر GET_INFO حتى DEVICE_INFO صالح.
- عند UART overflow أو buffer-full أو framing/parity/break error يفرغ stream ويعيد parser ويبطل metadata ويطلب DEVICE_INFO من جديد.
- القياسات المقبولة توضع في queue محدودة؛ عند امتلائها تسقط العينة الجديدة وتزيد عداد dropped_measurements بدلاً من حجب task.
- UART0 محفوظ للـconsole. UART1 هو المنفذ الافتراضي، لكن GPIO TX/RX غير معينة.

### الطرف المقابل RP2040
- UART0 GP0=TX وGP1=RX بسرعة 921600/8N1 إعداد مؤقت فقط؛ تحقق من طراز اللوحة وcontinuity قبل التوصيل.
- يستقبل HELLO/GET_INFO/START/STOP/SET_PROFILE/SELF_TEST ويرد ACK.
- GET_INFO يرسل DEVICE_INFO مع ADC_NONE وVREF=0 لأن ADC غير مركب.
- START مرفوض بسبب TX_NOT_ARMED؛ STOP يوقف اختبار التوقيت المنطقي فقط؛ SET_PROFILE يقبل profile 1، وSELF_TEST غير مدعوم.

## إعداد الأمان
- `CONFIG_REV_A_UART_ENABLE` افتراضياً `n`.
- `CONFIG_REV_A_UART_TX_GPIO` و`CONFIG_REV_A_UART_RX_GPIO` افتراضياً `-1`.
- يرفض البناء عند تفعيل UART دون GPIO محددة؛ لا تختر الأرجل من اسم الشريحة وحده.
- لا توصل GP4=TX_TEST إلى MOSFET أو ملف أو 12V. لا توجد مرحلة TX أو interlock عتادي.

## ADC وواجهة الهاتف
- ADS8861 PIO/DMA capture driver موجود في مشروع RP2040 ويُجمع في CI، لكنه `ENABLE_ADS8861_CAPTURE=0` افتراضياً؛ لا توجد قراءة ADC فعلية.
- لا توجد Wi-Fi AP أو WebServer JSON endpoints على ESP32-S3 بعد. تطبيق Android الحالي يتوقع `GET /status` و`POST /control`؛ لذلك لا يوجد تكامل هاتف↔جهاز حتى الآن.

## التحقق الآلي
- CI #1371 / run ID `43725575113` على commit `e37fde414924eed0344285e642b43982158f52eb`: كل الوظائف الأربع Success.
- 50 اختبار Python واختبار C parser/session صارم نجحا.
- ESP-IDF release-v5.4 compile/link نجح.
- RP2040 UF2 اجتاز فحص البنية وFamily ID `0xE48BFF56` ورفع كـartifact ID `14166064302`.
- رابط التشغيل: https://github.com/Khaledserdani/IslamDetector/actions/runs/43725575113

**حدود الإثبات:** نجاح CI يثبت البناء واختبارات المضيف فقط. لا يثبت UART loopback أو pin mux أو التوقيت الفعلي أو ADC/AFE أو القياس التناظري أو أداء الكشف. لا توجد قيم حماية TX/RX أو BOM/PCB نهائية.


### Invalid DEVICE_INFO recovery
A syntactically valid frame with inconsistent ADC metadata invalidates the session. The bridge now clears its mirrored public status snapshot and immediately retries GET_INFO, so stale ADC identity is not exposed after the session gate closes. This is host-code behavior pending fresh CI and hardware fault-injection/loopback; it is not a hardware test result.


### Profile identity gate
- The ESP32-S3 session rejects any MEASUREMENT whose profile_id differs from DEVICE_INFO.active_profile_id.
- Accepted session records retain profile_crc32 and info_generation so the sample can be traced to the exact advertised timing-profile revision.
- A mismatch counter is exposed in the UART bridge status snapshot. This is host-code validation; no board-to-board loopback is claimed.


## تحديث 2026-11-25 — واجهة Wi-Fi/HTTP آمنة أولية

- أضيف SoftAP اختياري وHTTP API متوافق مع مسارات Android: `GET /status` و`POST /control`.
- SoftAP معطل افتراضياً (`CONFIG_REV_A_WIFI_ENABLE=n)). عند الاختبار المحلي يجب ضبط SSID وكلمة مرور WPA2 خاصة بطول 8..63 حرفاً؛ لا تضع كلمة المرور في Git أو sdkconfig المرفوع.
- عنوان SoftAP الافتراضي في ESP-IDF هو `192.168.4.1`.
- `GET /status` يعيد signal/confidence/depth/calibration_percent كـnull، و`tx_armed=false` و`measurement_available=false` و`adc_present=false`. هذه حالة صادقة؛ لا توجد عينات أو قياسات وهمية.
- `POST /control`: أمر `stop` يعيد حالة idle الآمنة فقط؛ `start` يرفض بـHTTP 409 بسبب عدم وجود TX interlock معتمد؛ `calibrate` يرفض بـHTTP 409 لعدم وجود ADC مركب.
- Android يعطل زر البدء والمعايرة ما لم يعلن الجهاز صراحةً `tx_armed=true` أو `measurement_available=true`. لا يغيّر التطبيق حالة الكشف بتفاؤل بعد إرسال الأمر؛ يعيد قراءة `/status`.
- هذا تنفيذ برمجي اختياري لم يُشغّل على لوحة فعلية. لا يثبت SoftAP أو HTTP على العتاد، ولا يفعّل UART أو ADC أو TX.


### تصحيح إعدادات Kconfig — 2026-11-25

أظهر CI #2096 / run ID `45624352985` أن رمزي `CONFIG_REV_A_WIFI_SSID` و`CONFIG_REV_A_WIFI_PASSWORD` غير معرفين في `rev_a_http_api.c`. عند commit الفاشل كان ملف الإعدادات في جذر المشروع، ولم يكن `main/Kconfig` موجوداً. نُقلت إعدادات UART وWi-Fi إلى `main/Kconfig` بجانب `main/CMakeLists.txt`، وأضيف `#include "sdkconfig.h"` صراحةً إلى `app_main.c` و`rev_a_http_api.c`.

مقارنة GitHub أكدت أن الفرع يحتوي الآن هذين التغييرين بعد commit الفشل. هذا يتفق مع دليل Espressif الرسمي الذي يحدد جذر كل component موضعاً تلقائياً لاكتشاف `Kconfig` و`Kconfig.projbuild`. مع ذلك، لا يُعد التصحيح ناجحاً حتى ينجح بناء ESP32-S3 على commit لاحق. تبقى UART وSoftAP معطلتين افتراضياً، وGPIO غير معينة، وكلمة مرور SoftAP فارغة افتراضياً؛ لا تفعّلها قبل ضبط كلمة مرور خاصة ومراجعة pinout اللوحة.
