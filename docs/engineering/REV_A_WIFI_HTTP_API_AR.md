# واجهة Wi-Fi/HTTP الآمنة — Rev A

**التاريخ:** 2026-11-25  
**الحالة:** تنفيذ برمجي أولي اختياري؛ لم يختبر على لوحة فعلية.  
**الفرع:** `hardware/rev-a-measurement-design`

## 1. الهدف

توفير واجهة SoftAP محلية على ESP32-S3 تتوافق مع تطبيق Android الحالي دون إظهار قياسات مصطنعة أو فتح مرحلة TX قبل اكتمال الحماية.

## 2. الإعداد الآمن

- `CONFIG_REV_A_WIFI_ENABLE` افتراضياً `n`.
- لا يبدأ SoftAP إلا بعد تفعيل الخيار محلياً وضبط:
  - SSID بطول 1..32 byte.
  - WPA2 password خاص بطول 8..63 byte.
- لا تحفظ كلمة المرور في Git أو ترفع `sdkconfig` إلى المستودع.
- عنوان SoftAP الافتراضي: `192.168.4.1`.
- التشفير WPA2-PSK؛ لا يوجد AP مفتوح افتراضياً.
- إذا كانت كلمة المرور غير صالحة، لا يبدأ SoftAP ويستمر Firmware دون واجهة الهاتف.

## 3. GET /status

يعيد JSON بهذه الدلالات:

| الحقل | القيمة الحالية | المعنى |
|---|---|---|
| device | Islam Detector | اسم الجهاز |
| state | idle | لا توجد دورة كشف فعالة |
| signal | null | لا توجد عينة حقيقية |
| confidence | null | لا توجد نتيجة تحليل |
| depth_cm | null | لا يوجد تقدير عمق |
| calibrated | false | لا توجد معايرة معتمدة |
| calibration_percent | null | لا يوجد تقدم معايرة |
| tx_armed | false | لا يوجد interlock TX معتمد |
| measurement_available | false | لا يوجد مسار ADC فعلي متاح |
| adc_present | false | لا يوجد ADC مركب ومثبت |
| adc_model_id | 0 | لا يوجد طراز ADC معلن |
| device_info_valid | false | لا توجد هوية ADC موثقة |

لا تملأ هذه الحقول بأصفار قياس؛ تستخدم JSON null عندما تكون القيمة غير متاحة.

## 4. POST /control

Body: `{"command":"start|stop|calibrate"}`

| الأمر | HTTP | السلوك |
|---|---:|---|
| stop | 200 | قبول idempotent لحالة idle الآمنة؛ لا يوجد TX path ليتم إيقافه |
| start | 409 | رفض: `TX_INTERLOCK_NOT_IMPLEMENTED` |
| calibrate | 409 | رفض: `ADC_NOT_INSTALLED` |
| غير معروف | 400 | رفض الطلب |

سياسة الأوامر في C مستقلة عن خادم HTTP، ومغطاة باختبار C صارم ضمن protocol-tests. لا يرسل هذا الإصدار START إلى RP2040 ولا يتجاوز رفضه الحالي.

## 5. سلوك Android

- لا يتيح زر البدء إلا إذا أعلن الجهاز `tx_armed=true`.
- لا يتيح المعايرة إلا إذا أعلن الجهاز `measurement_available=true`.
- لا يفترض نجاح start/stop من مجرد نجاح POST؛ يعيد قراءة `/status` لتحديث الواجهة.
- عند غياب حقول القدرات، يتعامل معها التطبيق كـfalse، حفاظاً على الوضع الآمن.

## 6. حدود الإثبات والخطوات التالية

- CI يثبت compilation واختبار سياسة الأوامر فقط.
- لم يحدث flash على ESP32-S3، ولا اختبار SoftAP أو DHCP أو HTTP من هاتف Android.
- لا يثبت نجاح الاتصال أن UART أو ADC أو TX يعمل.
- بعد تحديد مراجعة لوحة ESP32-S3، يمكن إعداد WPA2 محلياً ثم اختبار SoftAP و`GET /status` أولاً.
- لا تفعّل UART حتى تثبيت GPIO من schematic اللوحة الفعلية. لا تفعّل ADC حتى تركيب الحماية وADC وقياس CONVST/SCLK/DOUT. يبقى START مرفوضاً حتى اعتماد interlock مستقل واختباره.

## 7. بناء الاختبار

```sh
cc -std=c11 -Wall -Wextra -Werror -pedantic \
  -Ifirmware/esp32_s3_bridge/main \
  firmware/esp32_s3_bridge/main/rev_a_http_api_policy.c \
  firmware/esp32_s3_bridge/tests/test_rev_a_http_api_policy.c \
  -o /tmp/rev_a_http_api_policy_test
/tmp/rev_a_http_api_policy_test
```


## تصحيح Kconfig — 2026-11-25

أظهر CI #2096 أن ملف Kconfig في جذر مشروع ESP-IDF لم يعرّف رموز Wi-Fi في build الخاص بمكوّن main. الإعدادات موجودة الآن في `firmware/esp32_s3_bridge/main/Kconfig` بجانب `main/CMakeLists.txt`، مع تضمين `sdkconfig.h` صراحةً. لا تزال Wi-Fi وUART معطلتين افتراضياً.
