# بروتوكول القياس بين RP2040 وESP32-S3 — Rev A

**الحالة:** عقد بيانات v0.1؛ مرجع Python ومحلل C محمول، وESP-IDF UART task ومستقبل أوامر RP2040/ACK منفذة برمجياً وتُبنى على CI. لم ينفذ UART loopback أو اختبار اللوحتين فعلياً بعد.  
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
| ADC_MODEL_ID | 1 | 0x00 لا يوجد ADC مركب؛ 0x01 ADS8861؛ 0x02 ADS8860؛ 0x03 ADS7054؛ 0x04 AD7980 |
| SAMPLE_FORMAT_ID | 1 | 0x00 غير متاح عند ADC_NONE؛ 0x01 two's-complement؛ 0x02 unsigned straight-binary |
| ADC_RESOLUTION_BITS | 1 | 16 أو14؛ صفر فقط عند ADC_NONE |
| ADC_INPUT_MODE_ID | 1 | 0x00 غير متاح عند ADC_NONE؛ 0x01 differential؛ 0x02 single-ended؛ 0x03 pseudo-differential |
| ADC_VREF_UV | 4 | قيمة المرجع الاسمية بالميكروفولت؛ ADS8861 مع ADR4540B=4096000؛ القيمة0 تعني أن قيمة المرجع لم تُقَس/لم تُحدَّد |
| ACTIVE_PROFILE_ID | 1 | جدول التأخيرات النشط |
| PROFILE_CRC32 | 4 | CRC32/ISO-HDLC لجدول الملف |

مرجع Python ومحلل C يدعمان MEASUREMENT وDEVICE_INFO وأوامر التحكم وACK. أضيف parser تدريجي مشترك يقبل fragmented/concatenated/noisy command وACK frames، مع CRC وSYNC recovery. يفرض Firmware قائمة profile IDs المسموحة؛ encoder لا يثبت أن الأمر آمن.

يجب على ESP32-S3 طلب DEVICE_INFO عند الاتصال أو إعادة الاتصال، وحفظ هذه البيانات مع جلسة القياس. عند ADS8861، يحول التطبيق raw16 إلى signed int16 وفق SAMPLE_FORMAT_ID=0x01، مع الاحتفاظ بالـraw الأصلي. إذا تغير ADC_MODEL_ID أو SAMPLE_FORMAT_ID، لا تخلط البيانات مع جلسة قديمة. تركيبات metadata المقبولة: ADS8861=(two's-complement,16,differential)، ADS8860=(unsigned,16,single-ended)، ADS7054=(two's-complement,14,differential)، AD7980=(unsigned,16,pseudo-differential). في ADS7054 يحفظ Firmware كود14-bit right-justified داخل حاوية16-bit، وتكون البتات العليا صفراً؛ يطبق التطبيق sign-extension من bit13 وفق ADC_RESOLUTION_BITS=14.

### 5.2 ترميز أوامر ESP32-S3

الدالة rev_a_encode_command() تنشئ إطاراً كاملاً بنفس SYNC/VERSION/LENGTH/CRC16:
- HELLO وGET_INFO وSTART وSTOP وSELF_TEST: لا payload، LENGTH=4، والإطار8 بايت.
- SET_PROFILE: بايت واحد فقط لمعرف الملف، LENGTH=5، والإطار9 بايت.
- ترفض الدالة أنواع الأوامر غير المعروفة وأطوال payload غير المطابقة والسعة غير الكافية.
- لا تعتمد الدالة profile ID ولا تثبت أنه آمن؛ يجب أن يتحقق RP2040 من allowlist ثابتة قبل تنفيذ SET_PROFILE.
- مستقبل RP2040 الحالي يقبل HELLO/GET_INFO/START/STOP/SET_PROFILE/SELF_TEST عبر UART0؛ ويرد ACK بصيغة موحدة. GET_INFO يرسل ACK ثم DEVICE_INFO.
- في Firmware الاختبار الحالي: START مرفوض دائماً لأن مرحلة TX وقفل الأمان غير موجودين؛ STOP آمن ومتكرر؛ SET_PROFILE يقبل المعرف1 فقط؛ SELF_TEST غير مدعوم حتى تركيب ADC.

### 5.3 صيغة ACK v0.1
بعد SYNC والرأس المشترك، يحتوي ACK على payload ثابت من3 بايتات، لذلك LENGTH=7 وإجمالي الإطار11 بايت:
| الحقل | الحجم | المعنى |
|---|---:|---|
| COMMAND_TYPE | 1 | نوع الأمر الذي يرد عليه ACK |
| STATUS | 1 | 0=OK، 1=REJECTED، 2=BUSY، 3=UNSUPPORTED |
| REASON | 1 | 0=NONE؛ 1=TX_NOT_ARMED؛ 2=ADC_NOT_PRESENT؛ 3=PROFILE_UNKNOWN؛ 4=SELF_TEST_UNAVAILABLE؛ 5=COMMAND_UNSUPPORTED |

قاعدة التحقق: STATUS=OK يتطلب REASON=NONE؛ وكل حالة غير OK تتطلب سبباً غير صفري. لا يوجد command sequence في v0.1، لذلك يجب تسلسل الأوامر وعدم إرسال أوامر متزامنة متعددة قبل معالجة ACK السابق. CRC16 يحسب بالطريقة نفسها من VERSION إلى آخر payload.

### 5.4 ADC_NONE ومنع القياسات الوهمية
- ADC_MODEL_ID=0x00 يعني أن المتحكم متصل لكن لا يوجد ADC مركب/معروف. عندها يجب أن تكون SAMPLE_FORMAT_ID=0 وADC_RESOLUTION_BITS=0 وADC_INPUT_MODE_ID=0 وADC_VREF_UV=0.
- يقبل parser/session هذه DEVICE_INFO كتعريف صادق لحالة اللوحة، لكنه يرفض كل MEASUREMENT ويرفع عداد rejected_measurements_without_adc. لا ترسل metadata ADS8861 المرشحة قبل تركيب ADC وتهيئته وقياس مرجعه.
- PROFILE_CRC32 في هذا الإصدار هو CRC32/ISO-HDLC على ثمانية أعداد delay_ns، كل منها uint32 Little Endian. profile 1 = 8000/12000/16000/24000/36000/52000/72000/100000ns، وقيمته 0x71E6D9DD. هذه هوية جدول التوقيت البرمجي وليست توقيتاً مقاساً على اللوحة.

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

أضيف إلى `tools/rev_a_protocol.py` محلل تدريجي `ProtocolStreamDecoder` (والاسم القديم `MeasurementStreamDecoder` محفوظ للتوافق) لمعالجة كل أنواع الإطارات في Rev A:
- MEASUREMENT وDEVICE_INFO وACK وأوامر HELLO/GET_INFO/START/STOP/SET_PROFILE/SELF_TEST.
- يقبل أجزاء الإطار حتى لو قُسمت بين عدة قراءات UART، ويعالج عدة إطارات متتابعة في buffer واحد.
- يتجاوز الضجيج قبل SYNC ويحافظ على بايت SYNC منفرد إذا وصل وحده في نهاية دفعة.
- يتحقق من VERSION وTYPE وطول الجسم قبل انتظار كامل الإطار، ثم يفحص CRC.
- عند تلف إطار يتقدم بايتاً واحداً ويبحث عن SYNC صالح لاحقاً بدلاً من إسقاط كامل buffer.
- يسجل عدد البايتات المهملة والإطارات المرفوضة للتشخيص.

يدعم المرجع أيضاً ADC_NONE كحالة صحيحة معلنة: sample format وinput mode غير متاحين، resolution=0 وVREF=0؛ ويرفض أي VREF غير صفري مع ADC_NONE. اختبارات الوحدة تغطي fragmentation وconcatenation والضجيج وفساد CRC واستعادة الإطار السليم التالي والأوامر وACK وADC_NONE. هذا مرجع برمجي ذهبي، ولا يمثل UART driver أو اتصالاً مادياً على ESP32.

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


## 8.4 UART task على ESP32-S3

أضيف مكوّن ESP-IDF rev_a_uart_bridge:
- RX ring buffer وevent queue وFreeRTOS task.
- استقبال fragmented/concatenated/noisy frames عبر parser الحالي؛ تغذية parser بايتاً بايتاً تسمح بإبطال metadata فور اكتشاف frame rejection.
- DEVICE_INFO يفتح جلسة ADC، وMEASUREMENT لا يصل إلى queue إلا بعد metadata صالحة.
- HELLO وGET_INFO عند بدء التشغيل، وإعادة GET_INFO كل ثانية حتى وصول DEVICE_INFO.
- UART FIFO overflow وbuffer full وparity/frame/break errors تمسح RX/parser وتبطل DEVICE_INFO ثم تطلبه مجدداً.
- القياسات المقبولة تحفظ raw16 وADC metadata وinfo_generation. عند امتلاء queue تسقط العينة الجديدة مع عداد واضح ولا توقف UART task.

**ملاحظة تاريخية قبل تحديث 2026-11-15:** كانت جهة RP2040 لم تنفذ command receiver أو ACK/DEVICE_INFO transmitter بعد. تم لاحقاً تنفيذ استقبال الأوامر وإرسال ACK وDEVICE_INFO=ADC_NONE كما يوثق القسم9؛ وما زال اختبار end-to-end وWi-Fi/Android endpoint غير مكتملين.


## 8.5 تحقق تكامل ESP32 وتحديد فجوة جهة RP2040 — 2026-11-14

- اكتمل بناء ESP-IDF bridge على CI #1319 (run ID `43604013988`) مع الوظائف الثلاث الأخرى. هذا compile/link للبرنامج فقط، ولا يثبت إرسال GET_INFO فعلياً على UART.
- أضيفت على ESP32 UART task تستخدم UART driver وRX ring buffer وevent queue وFreeRTOS task، وتغذي parser/session وتطلب GET_INFO كل ثانية حتى DEVICE_INFO صالح.
- لا يرسل RP2040 حالياً DEVICE_INFO ولا ينفذ HELLO/GET_INFO أو START/STOP/SET_PROFILE. لذلك لا يوجد handshake أو قياس end-to-end.
- ACK (`TYPE=0x80`) مذكور كنوع في جدول البروتوكول، لكن payload (command echo/status/reason/sequence) لم يُحدد بعد. محلل ESP32 الحالي يقبل DEVICE_INFO وMEASUREMENT فقط؛ أي ACK قبل إضافة decoder سيُعامل كإطار مرفوض وقد يؤدي إلى إبطال DEVICE_INFO وطلبه مجدداً. **لا تضف ACK من RP2040 قبل تثبيت بنية payload واختبار parser على الطرفين.**
- DEVICE_INFO يجب أن يصف ADC المركب فعلياً. لا ترسل metadata ADS8861 إذا لم يكن ADC موجوداً ومهيأ؛ لا نستخدم هوية مرشحة كأنها حقيقة.
- اختبارات C وPython على CI تثبت منطق framing/session على المضيف. لا تثبت UART peripheral أو baud/throughput أو استعادة الأخطاء على اللوحتين.
- الخطوة التالية: تعريف ACK بدقة، ثم تنفيذ command receiver وDEVICE_INFO transmitter على RP2040، وإضافة اختبارات host مشتركة للـencoder/decoder قبل UART loopback منخفض الجهد.



## 8.6 نتيجة CI #1320 — 2026-11-14

اكتملت الوظائف الأربع في CI #1320 على commit `61ab603` بنجاح؛ شملت 45 اختبار Python، واختبار C الصارم للـparser/session، وبناء ESP-IDF، وبناء RP2040 مع UF2 verification. لا يغير ذلك حدود البروتوكول: RP2040 لم ينفذ بعد command receiver أو DEVICE_INFO transmitter، وACK payload غير معرف. لذلك لا يوجد handshake فعلي بين المتحكمين، ولا يجوز اعتبار القياسات متاحة قبل DEVICE_INFO صحيحة من العتاد الحقيقي.


## 9. تنفيذ مستقبل RP2040 وACK — 2026-11-15
- أضيف استقبال UART0 بسرعة921600/8N1 على GP0=TX وGP1=RX في firmware الاختباري؛ اختيار الأرجل مؤقت ويحتاج مطابقة لوحة RP2040-Zero الفعلية وقياس continuity قبل التوصيل.
- يستعمل RP2040 نفس rev_a_parser_feed() المشترك لاستقبال fragmented/noisy commands مع CRC16 وSYNC recovery.
- HELLO وGET_INFO وSTOP وSET_PROFILE(profile 1) لها ACK؛ GET_INFO يرسل DEVICE_INFO بعد ACK.
- DEVICE_INFO الحالي يعلن ADC_NONE بوضوح، لأن ADC غير مركب. لا توجد قياسات ترسل من هذا البرنامج. START مرفوض بسبب غياب مرحلة TX وقفل أمان عتادي، وSELF_TEST غير مدعوم دون ADC.
- CRC32 للجدول profile 1 معرف على ثمانية تأخيرات ns بصيغة uint32 little-endian ويساوي 0x71E6D9DD.
- هذه نقطة تكامل برمجية قابلة للبناء؛ لا تثبت UART loopback أو صحة GP0/GP1 أو وجود ADC أو أداء تناظري.

## 9.1 توحيد مرجع Python مع رسائل التحكم — 2026-11-15

- أضيفت `encode_command/decode_command` لأوامر HELLO وGET_INFO وSTART وSTOP وSET_PROFILE وSELF_TEST، مع فحص طول payload وCRC16.
- أضيفت `encode_ack/decode_ack` بحمولة ثابتة3 بايت: COMMAND_TYPE وSTATUS وREASON؛ ويُفرض أن OK يقترن بـNONE، وأن الرفض/الانشغال/عدم الدعم له سبب غير صفري.
- أصبح `ProtocolStreamDecoder` يقبل أوامر وACK بالإضافة إلى DEVICE_INFO وMEASUREMENT، ويحتفظ باسم `MeasurementStreamDecoder` كاسم توافق قديم.
- أضيفت ADC_NONE إلى جدول metadata المرجعي؛ يمنع تفسير أي sample عند عدم وجود ADC، ويشترط VREF=0.
- CI #1365 (run ID `43724254180`) اجتاز وظيفة `protocol-tests`: 50 اختبار Python ثم C parser/session build/test مع `-Wall -Wextra -Werror -pedantic`. كانت وظائف Android وESP32-S3 وRP2040 قيد التنفيذ وقت التوثيق؛ لا تسجل نجاح CI الكامل قبل اكتمالها.
- لا يثبت هذا اختبار UART loopback أو board-to-board أو وجود ADC مركب.


## 9.2 حالة التنفيذ بعد CI #1371 — 2026-11-15

- ACK v0.1 مثبت بحمولة 3 بايتات: `COMMAND_TYPE` و`STATUS` و`REASON`. يقبل parser تراكيب status/reason المتوافقة فقط؛ OK يتطلب NONE، وأي رفض/انشغال/عدم دعم يتطلب سبباً غير صفري.
- RP2040 يستقبل HELLO وGET_INFO وSTART وSTOP وSET_PROFILE وSELF_TEST على UART0/GP0/GP1 بسرعة921600/8N1 (الأرجل مؤقتة). يرد ACK؛ GET_INFO يرسل DEVICE_INFO بعده.
- DEVICE_INFO الحالي يعلن ADC_NONE مع SAMPLE_FORMAT_UNKNOWN وresolution=0 وinput=UNKNOWN وVREF=0. لذلك لا تقبل session أي MEASUREMENT حتى يعلن ADC مركباً وmetadata صحيحة.
- START مرفوض بسبب TX_NOT_ARMED؛ لا MOSFET ولا ملف ولا interlock عتادي في هذا firmware. STOP يوقف اختبار التوقيت المنطقي فقط.
- ESP32-S3 parser/session وUART task بُنيا على ESP-IDF release-v5.4. الجسر يرسل HELLO ثم GET_INFO ويعيد الطلب حتى وصول DEVICE_INFO، ويعالج ACK ويضع القياسات المقبولة في queue محدودة. UART bridge معطل افتراضياً وGPIO=-1.
- CI #1371 / run ID `43725575113`: 50 اختبار Python ناجح، واختبار C صارم ناجح، وبناء ESP32-S3 وRP2040 وAndroid ناجح. لا يثبت ذلك UART loopback أو الاتصال الفعلي بين اللوحتين.
- لا توجد بعد عينات MEASUREMENT من ADC حقيقي، ولا Wi-Fi/WebServer API. Android يتوقع `GET /status` و`POST /control`؛ الربط بين واجهة الهاتف والجسر لم ينفذ بعد.


## 9.3 تحقق CI #1379 وحدود مسار القياس — 2026-11-17

- CI #1379 / run ID `43884818868` نجح على HEAD `e68714446555172c92f67d81f8132ff66743cd38`؛ 50 اختبار Python نجحت، كما نجح بناء واختبار C parser/session مع التحذيرات الصارمة.
- اختبارات البروتوكول تغطي fragmented/concatenated/noisy/corrupt frames وSYNC recovery، أوامر HELLO/GET_INFO/START/STOP/SET_PROFILE/SELF_TEST، ACK status/reason، وDEVICE_INFO/ADC metadata.
- ESP32-S3 UART task يقبل ACK وDEVICE_INFO وMEASUREMENT عبر parser/session، ويبطل metadata ويعيد GET_INFO بعد أخطاء stream أو DEVICE_INFO غير صالح. قبول MEASUREMENT مشروط بـDEVICE_INFO صالحة وADC غير NONE؛ raw16 محفوظ مع interpreted values محكومة بالـmetadata وVALID_MASK.
- RP2040 يرسل ACK وDEVICE_INFO=ADC_NONE حالياً؛ لذلك لا يرسل MEASUREMENT حقيقية. لا توجد ADS8861 مركبة أو عينات ADC فعلية، ولا UART loopback على لوحتين.
- لا يُغيّر CI الناجح هذه الحدود: build host/compile ليس إثبات baud أو framing أو queue behavior على العتاد، ولا يثبت Wi-Fi أو Android endpoint.
- الخطوة التالية بعد loopback: تركيب ADC والمرجع والحماية المقاسة، ثم MEASUREMENT producer مع sequence/timestamp/profile/flags وraw16، واختبار round-trip عبر C/Python قبل تمريرها إلى Android.


## 9.5 مراجعة الحالة الفعلية — 2026-11-19

- جهة RP2040 تنفذ command receiver على UART0، وترد ACK على HELLO/GET_INFO/STOP/SET_PROFILE/START/SELF_TEST. START مرفوض بـTX_NOT_ARMED، وGET_INFO يرسل DEVICE_INFO=ADC_NONE؛ هذا سلوك firmware برمجي، وليس UART loopback على لوحة فعلية.
- جهة ESP32-S3 تحتوي C parser/session ومهمة UART تستقبل ACK وDEVICE_INFO وMEASUREMENT، وتبطل metadata وتطلب GET_INFO مجدداً بعد أخطاء stream. الجسر معطل افتراضياً وGPIO TX/RX غير معينين حتى مطابقة لوحة N16R8.
- PIO ADS8861 موجود في `ads8861_capture.pio` و`ads8861_capture.c`، مع GP8/GP9/GP10 وDMA وثماني نوافذ. لكنه معطل افتراضياً عبر `ENABLE_ADS8861_CAPTURE=0`؛ لا توجد لوحة ADC موصولة أو قياسات فعلية.
- لا يوجد حالياً MEASUREMENT producer يرسل sweep عبر UART؛ عند تفعيل المسار الاختباري، عينات RAW16 تُطبع عبر USB debug فقط. لا توجد سلسلة ADC→UART→ESP32→Wi-Fi→Android.
- يجب أن تبقى DEVICE_INFO=ADC_NONE حتى تركيب ADC فعلياً والتحقق من تغذيته ومرجعه ونمط دخله. لا تعلن ADS8861 أو VREF مرشحاً على أنه حقيقة مركبة.
- لا تخلط DD32 baseline مع نماذج Mono Spiral القديمة؛ لا تُستخدم قيم L/R/clamp المستخرجة من نموذج Mono Spiral لحسابات DD32.

## 9.4 نقطة تدقيق التكامل — 2026-11-18

- لم يتغير تنسيق UART binary v0.1 أو CRC16 أو بنية DEVICE_INFO في هذا التحديث.
- RP2040 الحالي يعلن ADC_NONE؛ لذلك لا يجوز إرسال أو قبول MEASUREMENT حقيقي حتى تركيب ADC وإعلان ADC_MODEL_ID وSAMPLE_FORMAT_ID وVREF والـinput mode المطابقة.
- ESP32 parser/session موجودان، لكن لا يوجد بعد end-to-end stream من ADC إلى UART ثم Wi-Fi/Android. لا تعتبر نجاح اختبارات decoder بديلاً عن اختبار اللوحتين.
- CI #1418 على `e44d5f7` انتهى بـstartup_failure قبل إنشاء أي Job؛ آخر تحقق كامل ناجح يظل CI #1379 على `e687144`، ولا يسجل هذا التحديث نجاحاً جديداً للبناء.


## 9.6 تدقيق محاذاة RAW16 لواجهة ADS8861 — 2026-11-19

- خرج ADS8861 متسلسل MSB-first؛ لذلك يجب أن يستخدم RP2040 PIO اتجاه IN shift-left مع autopush=16 حتى تبقى الكلمة الأصلية في ISR[15:0] دون عكس ترتيب البتات.
- صُحح الإعداد من shift-right إلى shift-left في ads8861_capture.c، وأضيف اختبار static guard بنمط 0xA55A. استخراج DMA الحالي capture_buffer[i] & 0xFFFF أصبح متوافقاً مع هذا الاتجاه.
- هذا يثبت اتساقاً برمجياً/حسابياً فقط؛ لا توجد قراءة ADC فعلية أو loopback أو قياس logic-analyzer حتى الآن. يبقى DEVICE_INFO=ADC_NONE وENABLE_ADS8861_CAPTURE=0 حتى تركيب ADC والتحقق منه.
