# إسلام V2 Rev A — نقطة استئناف موثقة

**التاريخ:** 2026-11-28  
**المستودع:** `Khaledserdani/IslamDetector`  
**الفرع:** `hardware/rev-a-measurement-design`  
**PR:** #7 (Draft، غير مدمج)  
**Workflow run:** #2120 — ID `46012326678`  
**المحاولة:** 2  
**Commit الذي اختُبر:** `620930f31ad2b36a4f8be45400b4abbc868eccdb`

## نتيجة البناء

اكتملت المحاولة الثانية بنجاح، وجميع وظائف CI الأربع ناجحة:

| الوظيفة | النتيجة |
|---|---|
| Protocol tests (Python/C + HTTP policy) | PASS |
| RP2040 firmware + UF2 verification | PASS |
| Android APK + ZIP integrity verification | PASS |
| ESP32-S3 ESP-IDF build | PASS |

المحاولة الأولى فشلت بسبب عطل خارجي في مستودع Microsoft APT (HTTP 403) أثناء تثبيت اعتماديات RP2040، وبسبب فشل بناء Android في المحاولة الأولى. أُعيد تشغيل الوظائف الفاشلة فقط، ونجحت المحاولة الثانية دون تغيير كود المشروع.

## Artifacts المنشورة

- `IslamDetector-Original-APK` — 21,735 bytes.
- `IslamDetector-RevA-RP2040-Timing-Test-UF2` — 30,262 bytes.
- `IslamDetector-RevA-ESP32S3-BUILD-ONLY` — 118,792 bytes (موجود من التشغيل السابق الناجح).

رابط التشغيل:
https://github.com/Khaledserdani/IslamDetector/actions/runs/46012326678

## ما الذي تثبته هذه النتيجة؟

تثبت أن مشروع Android يبنى، وأن firmware الخاص بـRP2040 يُترجم ويجتاز فحص بنية UF2 وFamily ID، وأن مشروع ESP32-S3 يُترجم بواسطة ESP-IDF، وأن اختبارات البروتوكول وسياسة HTTP تمر.

**لا تثبت** أن APK جُرّب على هاتف فعلي، أو أن UF2 فُلش على لوحة، أو أن UART بين اللوحتين يعمل كهربائياً، أو أن ADC يلتقط إشارة تناظرية صحيحة، أو أن ملف البحث/مرحلة TX يعملان ميدانياً.

## الحواجز المتبقية قبل تشغيل الجهاز

1. تثبيت طراز لوحة ESP32-S3 الفعلية ومراجعة pinout الخاص بلوحة التطوير؛ اسم الشريحة وحده لا يكفي.
2. اعتماد أرجل UART1 على لوحة ESP32-S3، مع إبقاء 921600 baud إعداداً برمجياً لا توصيلاً معتمداً.
3. إجراء UART loopback واختبار ربط منخفض الجهد بين RP2040 وESP32-S3.
4. تركيب ADS8861 فعلياً مع تغذية ومرجع وحماية AFE صحيحة، ثم قياس CONVST/SCLK/DOUT وتوقيت النوافذ على الأرجل.
5. إضافة مسار MEASUREMENT producer إلى UART بعد قبول ADC الحقيقي؛ حالياً RP2040 يرسل DEVICE_INFO بقيمة ADC_NONE ولا يرسل عينات قياس.
6. مراجعة AFE التفاضلي DD32، وحماية RX، واستعادة المضخم بعد تشبع TX.
7. إكمال قفل TX العتادي المستقل (one-shot، overcurrent comparator، fault latch، watchdog/UVLO) واختباره على حمل بديل محدود التيار قبل توصيل ملف البحث.
8. بعد اجتياز الاختبارات السابقة: دمج القياسات في واجهة Wi-Fi، ثم التحقق من Android على الهاتف، ثم اختبار ميداني مضبوط.

## إعدادات الأمان التي يجب عدم تغييرها حالياً

- `ENABLE_ADS8861_CAPTURE=0`.
- `CONFIG_REV_A_UART_ENABLE=n` افتراضياً إلى حين اعتماد أرجل لوحة ESP32-S3.
- `CONFIG_REV_A_WIFI_ENABLE=n` افتراضياً إلى حين ضبط WPA2 credentials محلياً.
- أمر START مرفوض؛ لا يوجد TX interlock عتادي معتمد.
- GP4 في RP2040 خرج اختبار منطقي فقط؛ ممنوع توصيله ببوابة MOSFET أو ملف أو مصدر 12V.
- لا تدمج PR #7 ولا تنقل التغييرات إلى `main` تلقائياً.

## الخطوة التالية

حسم طراز لوحة ESP32-S3 التطويرية الفعلية، ثم إغلاق UART loopback منخفض الجهد. لا حاجة لإعادة بناء APK أو UF2 قبل وجود تغيير في الكود أو إعدادات البناء.
