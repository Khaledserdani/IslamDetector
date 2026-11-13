# بروتوكول القياس بين RP2040 وESP32-S3 — Rev A

**الحالة:** عقد بيانات v0.1؛ مرجع Python ومحلل C محمول منفذان ومختبران على CI، لكن ESP-IDF UART task والربط الفيزيائي لم ينفذا بعد.  
**التاريخ:** 2026-11-11

## 1. الهدف

فصل توقيت PI وجمع العينات عن Wi-Fi. ينفذ RP2040 دورة القياس ويرسل إطارات مكتملة إلى ESP32-S3. يتولى ESP32-S3 عرض الحالة وتخزينها وإرسالها للهاتف.

- RP2040: التوقيت، TX pulse، ADC capture، فحوص صلاحية العينة.
- ESP32-S3: Wi-Fi/WebServer، إدارة التطبيق، التخزين المؤقت، النقل للهاتف.
- لا يسمح لانقطاع Wi-Fi بتغيير توقيت القياس أو ترك بوابة MOSFET في حالة تشغيل.

## 2. النقل الفيزيائي

- UART TTL بجهد منطقي 3.3V بين اللوحتين، مع أرضي مشترك منخفض الضوضاء.
- السرعة الأولية: 921600 baud، 8 data bits، no parity، 1 stop bit.
- خطوط TX/RX قصيرة داخل العلبة، ولا تمر بمحاذاة Drain أو ملف TX.
- يختبر فقد البيانات وCRC تحت تشغيل Wi-Fi وإرسال حزم متواصلة.
- لا توصل UART إلى مستوى 5V.

## 3. صيغة إطار القياس الثنائي

كل الأعداد متعددة البايتات Little Endian. حجم الترويسة ثابت 31 بايت، ثم عينات 16-bit، ثم CRC16. إطار MEASUREMENT يمثل **Sweep مكتمل من نبضة TX واحدة**: العينات الثماني تؤخذ داخل اضمحلال النبضة نفسها عند التأخيرات المحددة في PROFILE_ID بعد هبوط TX. هذا يحافظ على ترابط القياسات زمنياً ومكانياً ولا يخلط منحنيات اضمحلال من نبضات متعاقبة.

| الإزاحة | الحجم | الحقل | الوصف |
|---:|---:|---|---|
| 0 | 2 | SYNC | ثابت 0x49 0x53 (ASCII: IS) |
| 2 | 1 | VERSION | إصدار البروتوكول، يبدأ بـ 1 |
| 3 | 1 | TYPE | نوع الرسالة؛ 0x10 = MEASUREMENT |
| 4 | 2 | LENGTH | طول المحتوى من VERSION حتى آخر عينة، دون SYNC وCRC |
| 6 | 4 | SEQUENCE | عداد متزايد لكل إطار |
| 10 | 4 | TIMESTAMP_US | وقت هبوط TX (مرجع النوافذ الثماني) بالميكروثانية من بدء التشغيل |
| 14 | 1 | PROFILE_ID | معرف جدول النوافذ |
| 15 | 2 | FLAGS | أعلام حالة القياس |
| 17 | 4 | PULSE_WIDTH_NS | عرض نبضة TX بالنانوثانية |
| 21 | 2 | PULSE_RATE_HZ | معدل النبضات |
| 23 | 2 | SUPPLY_MV | أقل جهد تغذية مسجل خلال نبضة TX/التقاطها بالملي فولت |
| 25 | 2 | TX_CURRENT_MA | أعلى تيار TX مسجل خلال النبضة بالملي أمبير؛ 0xFFFF = غير متاح |
| 27 | 2 | TEMP_CENTI_C | حرارة اللوحة × 100؛ 0x7FFF = غير متاح |
| 29 | 1 | VALID_MASK | bit i = 1 إذا كانت العينة i صالحة |
| 30 | 1 | SAMPLE_COUNT | عدد العينات المرفقة، 1..8؛ Sweep الكامل يحتوي 8 |
| 31 | 2×N | SAMPLES | أكواد ADC الخام 16-bit؛ تحفظ قيمة ADC دون تحويل مزيف إلى µV |
| آخر 2 | 2 | CRC16 | CRC-16/CCITT-FALSE، polynomial 0x1021، init 0xFFFF، xorout 0 |

CRC يحسب من VERSION حتى آخر عينة، ولا يشمل SYNC أو بايتي CRC. تحفظ عينات ADC كـraw 16-bit words دون تحويل؛ تفسيرها يعتمد على ADC_MODEL_ID وSAMPLE_FORMAT_ID في رسالة DEVICE_INFO. ADS8861 مثلاً يخرج two's-complement signed؛ ADS8860 يخرج straight-binary unipolar؛ ADS7054 يحمل14-bit داخل حاوية16-bit. لا يجوز تفسير كل عينات ADC على أنها unsigned أو signed من دون metadata.

### أعلام FLAGS المقترحة

- bit 0: RX_CLIPPED — خرج الاستقبال أو ADC تجاوز المجال.
- bit 1: RX_RECOVERING — لم تستعد الواجهة بعد من نبضة TX.
- bit 2: TX_CURRENT_LIMIT — تجاوز حد تيار الحماية.
- bit 3: SUPPLY_FAULT — خلل تغذية.
- bit 4: TEMP_WARNING — تحذير حراري.
- bit 5: CALIBRATION_VALID — معايرة المسار المرجعي صالحة.
- bit 6: PROFILE_VALID — معرف النوافذ يطابق الجدول النشط.
- bit 7: ADC_FAULT — فشل قراءة أو تزامن ADC.
- bit 8: SWEEP_COMPLETE — اكتملت النوافذ الثماني داخل نبضة TX الواحدة لهذا الإطار.
- بقية البتات محجوزة وتبقى صفراً في الإصدار 1.

## 4. جدول النوافذ

الملف الأولي يحمل 8 نقاط تأخير مرشحة: 8، 12، 16، 24، 36، 52، 72، 100 µs بعد هبوط TX. يلتقط RP2040 النقاط الثماني داخل اضمحلال نبضة TX واحدة بواسطة PIO مع DMA لتفريغ RX FIFO، ثم يرسل إطار Sweep واحداً يحتوي العينات بترتيب جدول PROFILE_ID. زمن الالتقاط المقدر ينتهي قرب 103µs بعد هبوط TX، قبل النبضة التالية عند PRF=100Hz أو حتى1kHz. يرسل RP2040 جدول الملف النشط عند HELLO/GET_INFO أو SET_PROFILE.

يجب أن تتضمن رسالة وصف الملف:
- عدد النوافذ.
- كل تأخير بوحدة ns أو µs مع وحدة ثابتة محددة في البروتوكول.
- عرض النبضة ومعدل التكرار المسموحين.
- نسخة جدول الملف أو CRC له.

لا يعتمد أول تأخير حتى يثبت بالراسم أن RX خرج من القص والتشبع وأصبح مستقراً. إذا كانت نافذة غير صالحة، يخفض VALID_MASK ولا يملأها بقيمة صفر تبدو كأنها قياس حقيقي.

## 5. رسائل التحكم

كل أمر من ESP32-S3 إلى RP2040 يمر بإطار مستقل مع نفس SYNC/VERSION/LENGTH/CRC. الأنواع الأولية:

| TYPE | الاسم | الوظيفة |
|---:|---|---|
| 0x01 | HELLO | طلب تعريف المتحكم وإصدار Firmware |
| 0x02 | GET_INFO | طلب حالة الجهاز وملف القياس النشط |
| 0x03 | START | بدء القياس باستخدام ملف آمن معتمد |
| 0x04 | STOP | إطفاء TX وإيقاف دورة القياس |
| 0x05 | SET_PROFILE | اختيار ملف من قائمة ملفات مسموحة فقط |
| 0x06 | SELF_TEST | فحص المسار المرجعي الداخلي عند توقف القياس |
| 0x80 | ACK | تأكيد الأمر أو رفضه مع سبب |
| 0x82 | DEVICE_INFO | معلومات ADC/المرجع/صيغة العينة/الملف النشط |

في Rev A، لا يقبل SET_PROFILE أرقاماً عشوائية لعرض النبضة أو تيارها أو معدلها. يختار فقط ملفاً معرفاً مسبقاً ومسموحاً في Firmware. لا يسمح بتعديل ملفات الإثارة أثناء نبضة قائمة؛ يطبق التغيير عند توقف القياس وبعد ACK.

### 5.1 رسالة DEVICE_INFO

يرد RP2040 على GET_INFO برسالة DEVICE_INFO (TYPE=0x82). بعد SYNC يكون الرأس المشترك VERSION(1)+TYPE(1)+LENGTH(2)، ثم payload ثابت17 بايت Little Endian، ثم CRC16؛ لذلك LENGTH=21 وإجمالي الإطار25 بايت:
| الحقل | الحجم | المعنى |
|---|---:|---|
| HW_REV | 1 | مراجعة لوحة القياس |
| FW_MAJOR/MINOR/PATCH | 3 | إصدار Firmware |
| ADC_MODEL_ID | 1 | 0x01 ADS8861؛ 0x02 ADS8860؛ 0x03 ADS7054؛ 0x04 AD7980 |
| SAMPLE_FORMAT_ID | 1 | 0x01 two's-complement؛ 0x02 unsigned straight-binary |
| ADC_RESOLUTION_BITS | 1 | 16 أو14 |
| ADC_INPUT_MODE_ID | 1 | 0x01 differential؛ 0x02 single-ended؛ 0x03 pseudo-differential |
| ADC_VREF_UV | 4 | قيمة المرجع الاسمية بالميكروفولت؛ ADS8861 مع ADR4540B=4096000؛ القيمة0 تعني أن قيمة المرجع لم تُقَس/لم تُحدَّد |
| ACTIVE_PROFILE_ID | 1 | جدول التأخيرات النشط |
| PROFILE_CRC32 | 4 | CRC32/ISO-HDLC لجدول الملف |

مرجع Python الحالي يدعم MEASUREMENT وDEVICE_INFO في stream decoder؛ رسائل ACK وأوامر التحكم ما زالت مواصفة وليست تنفيذاً برمجياً كاملاً.

يجب على ESP32-S3 طلب DEVICE_INFO عند الاتصال أو إعادة الاتصال، وحفظ هذه البيانات مع جلسة القياس. عند ADS8861، يحول التطبيق raw16 إلى signed int16 وفق SAMPLE_FORMAT_ID=0x01، مع الاحتفاظ بالـraw الأصلي. إذا تغير ADC_MODEL_ID أو SAMPLE_FORMAT_ID، لا تخلط البيانات مع جلسة قديمة. تركيبات metadata المقبولة: ADS8861=(two's-complement,16,differential)، ADS8860=(unsigned,16,single-ended)، ADS7054=(two's-complement,14,differential)، AD7980=(unsigned,16,pseudo-differential). في ADS7054 يحفظ Firmware كود14-bit right-justified داخل حاوية16-bit، وتكون البتات العليا صفراً؛ يطبق التطبيق sign-extension من bit13 وفق ADC_RESOLUTION_BITS=14.

## 6. سلوك الأمان

1. حالة الإقلاع الافتراضية: TX_OFF، والبوابة منخفضة، وقياس PI متوقف.
2. إذا فشل CRC أو VERSION أو LENGTH، يهمل الإطار ولا ينفذ الأمر.
3. إذا توقف RP2040 أو لم يعد يرسل Heartbeat، يجب أن تعيد دارة العتاد نفسها بوابة MOSFET إلى OFF؛ لا يعتمد هذا الأمان على Wi-Fi أو التطبيق.
4. إذا تجاوز تيار TX أو حرارة اللوحة حدود الاختبار، يوقف القياس ويصدر FAULT.
5. STOP له أولوية على START وSET_PROFILE.
6. عند انقطاع ESP32-S3، يتوقف استقبال أوامر جديدة؛ سياسة استمرار القياس أو إيقافه تكون محددة مسبقاً، والأكثر أماناً في Rev A هو إيقاف TX بعد مهلة Heartbeat قصيرة.
7. لا تحفظ القراءة إذا كانت RX_CLIPPED أو RX_RECOVERING أو ADC_FAULT؛ يمكن حفظها في سجل تشخيص منفصل مع سبب عدم الصلاحية.

## 7. ميزانية النقل

مع 8 عينات × 2 بايت، وحجم إطار يقارب 49 بايت، وكل إطار يمثل Sweep من **نبضة TX واحدة**:
- عند 100 نبضة/ثانية: نحو 4.9 kB/s.
- عند 500 نبضة/ثانية: نحو 24.5 kB/s.
- عند 1000 نبضة/ثانية: نحو 49 kB/s.
- UART 921600 baud مع 8N1 يوفر نظرياً نحو 92.16 kB/s؛ عند 1kHz يشغل الإطار قرابة53% من السعة النظرية قبل أي رسائل إضافية. يجب قياس throughput الفعلي وفقد الإطارات تحت حمل Wi-Fi، وإضافة buffer كافٍ.

## 8. شروط قبول البروتوكول

- اختبار CRC مع إطارات صحيحة وتالفة.
- كشف الإطار المفقود أو المكرر عبر SEQUENCE.
- كشف انقطاع/التفاف TIMESTAMP وعدم تفسيره كزمن سالب.
- إثبات أن كل إطار Sweep يطابق PROFILE_ID الفعلي، ويحتوي النوافذ الثماني من نبضة واحدة بترتيب تأخيرات الملف؛ قياس التوقيتات الثماني على GP4/CONVST وDOUT قبل دمجها.
- قياس معدل النقل المستمر دون فقد في ظروف Wi-Fi القصوى.
- اختبار أن STOP وFAULT يطفئان TX حتى عند تعطل التطبيق.
- حفظ نسخة البروتوكول مع بيانات التجربة، حتى لا تختلط مجموعات البيانات عند تغييره.

### 8.1 محلل تدفق UART في المرجع البرمجي

أضيف إلى `tools/rev_a_protocol.py` محلل تدريجي `MeasurementStreamDecoder` لمعالجة استقبال UART الحقيقي:
- يقبل أجزاء الإطار حتى لو قُسمت بين عدة قراءات UART.
- يعالج عدة إطارات متتابعة في buffer واحد.
- يتجاوز الضجيج قبل SYNC ويحافظ على بايت SYNC منفرد إذا وصل وحده في نهاية دفعة.
- يتحقق من VERSION وTYPE وطول الجسم قبل انتظار كامل الإطار، ثم يفحص CRC.
- عند تلف إطار يتقدم بايتاً واحداً ويبحث عن SYNC صالح لاحقاً بدلاً من إسقاط كامل buffer.
- يسجل عدد البايتات المهملة والإطارات المرفوضة للتشخيص.

اختبارات الوحدة تغطي fragmentation وconcatenation والضجيج وفساد CRC واستعادة الإطار السليم التالي. يبقى هذا مرجع Python الذهبي للمقارنة؛ لا يمثل UART driver على ESP32.

### 8.2 محلل C محمول لجهة ESP32-S3

أضيف المكوّن `firmware/esp32_s3_bridge/components/rev_a_protocol/`، وهو C11 مستقل عن ESP-IDF ويمكن إدراجه كمكوّن ESP-IDF. واجهته `rev_a_parser_feed()` تستقبل أي أجزاء من UART وتصدر الإطارات الصحيحة عبر callback، مع:
- تحقق SYNC/VERSION/TYPE/LENGTH وCRC-16/CCITT-FALSE.
- تحليل MEASUREMENT المتغير من عينة إلى8 عينات مع فحص SAMPLE_COUNT وVALID_MASK وSWEEP_COMPLETE ومعدل النبض.
- تحليل DEVICE_INFO بطول ثابت25 بايت، والتحقق من توافق ADC_MODEL_ID وSAMPLE_FORMAT_ID وADC_RESOLUTION_BITS وADC_INPUT_MODE_ID.
- الاحتفاظ بكل عينة raw16، وتوفير `rev_a_interpret_sample()` لتفسيرها فقط عند تمرير metadata؛ ويعالج ADS7054 كـ14-bit right-justified مع sign extension.
- استعادة SYNC بعد الضجيج أو CRC تالف، ودعم fragmented وconcatenated frames دون تخصيص ذاكرة ديناميكي.

أضيف اختبار C مستقل `firmware/esp32_s3_bridge/tests/test_rev_a_protocol.c` يغطي متجه CRC المعروف، MEASUREMENT، DEVICE_INFO، رفض metadata غير المتسقة، signed16/signed14، fragmentation، الضجيج، تعدد الإطارات، واستعادة الإطار السليم بعد إطار تالف. يترجم CI هذا المكوّن مع `-Wall -Wextra -Werror -pedantic` ويشغل الاختبار.

**حدود الإثبات:** نجاح اختبار C على Linux لا يثبت تشغيل UART peripheral أو FreeRTOS على ESP32-S3. ما زال يلزم تنفيذ UART task مع RX ring buffer/overflow handling، إرسال GET_INFO/HELLO من ESP32، تخزين DEVICE_INFO قبل تفسير العينات، ثم Hardware UART loopback بين اللوحتين. لا توجد نتائج عتاد فعلية حتى الآن.


### 8.3 بوابة جلسة DEVICE_INFO قبل تفسير العينات

أضيفت طبقة C محمولة rev_a_session.c/.h فوق محلل الإطارات، لتطبيق شرط البروتوكول برمجياً بدلاً من تركه ملاحظة على مستدعي الدالة:

- تحتفظ كل جلسة UART ببنية rev_a_session_t مستقلة.
- لا تقبل MEASUREMENT للتحليل قبل وصول DEVICE_INFO صحيح؛ يزداد عداد الرفض وتعود الحالة REV_A_SESSION_WAITING_FOR_DEVICE_INFO.
- عند قبول DEVICE_INFO تحفظ هوية ADC وصيغة العينة والدقة ونمط الدخل وVREF ونسخة metadata generation.
- كل سجل مقبول يحمل نسخة metadata مع raw الكامل 16-bit. لا تفسر إلا البتات المحددة في VALID_MASK، وتبقى الكلمات الخام للنوافذ غير الصالحة محفوظة دون استبدالها بصفر.
- rev_a_session_invalidate_device_info() تبطل metadata عند UART overflow أو reconnect أو framing loss أو reset؛ بعدها يجب طلب DEVICE_INFO جديد قبل متابعة القياس.
- اختبارات C تغطي ADS8861 signed-16 وADS7054 right-justified signed-14، ورفض القياس قبل التعريف، وتغيير نوع ADC، وبقاء raw invalid window، وإبطال الجلسة.

**حدود الإثبات:** هذه طبقة جلسة محمولة ومختبرة على مضيف CI، وليست بعد ESP-IDF UART task أو FreeRTOS ring buffer أو GET_INFO فعلياً على ESP32-S3. لا يوجد UART loopback بين اللوحتين.
