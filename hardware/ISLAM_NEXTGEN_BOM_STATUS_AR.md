# حالة قائمة شراء ISLAM NEXTGEN — BOM Status

التاريخ: 2026-11-14
الحالة: **قائمة مرشحين وليست أمر شراء**. لا يُشترى أي مكوّن موسوم «غير معتمد».

## 1. وحدات التحكم والاتصال

| القطعة | العدد | الدور | التوفر | القرار |
|---|---:|---|---|---|
| NUCLEO-G474RE | 1 | MCU للـTX/AFE/ADC/HRTIM/COMP | لم يظهر مخزون جزائري مؤكد؛ شراء دولي محتمل | اختيار معماري محسوم، شراء مؤجل |
| ESP32-S3 N16R8 DevKitC-1 | 1 | Wi-Fi/WebServer/Firmware bridge | عرض محلي TIKNO مع headers ملحومة مسبقاً؛ السعر الظاهر 2500 دج +300 دج للحام | مرشح شراء محلي بعد تأكيد المخزون |

## 2. AFE والتناظرية

| القطعة | العدد المبدئي | الدور | التوفر | القرار |
|---|---:|---|---|---|
| OPA1612 SOIC-8 | 2 | gyrator + coil preamp + differential + monitor | لم يثبت محلياً | مرشح أولي، غير معتمد |
| AD8336 LFCSP16 | 1 | bucking VGA DC-coupled | لا مخزون جزائري مؤكد؛ استيراد/تجميع مصنع | مرشح محدد، غير معتمد |
| OPA2365 SOIC-8 | 1 | buffer/driver لقناتي ADC على3.3V | لم يثبت محلياً | مرشح واجهة ADC |
| TMUX6219 | 2 | SWb + high-gain blanking/enable على ±12V | لا مخزون جزائري مؤكد | مرشح محدد، غير معتمد |
| منظم 9V منخفض الضجيج | 1 | توليد VDCb=9V من +12V_AFE | لم يحدد النوع | غير محسوم |
| MCP41HV51-104E/ST | 1 | digital pot100kΩ، 8-bit/256 taps، SPI، أطراف±18V، TSSOP-14 لضبط Rvar | لم يثبت محلياً؛ Microchip In Production | مرشح محدد، غير معتمد حتى محاكاة terminal voltage والتسلسل |
| مقاومة دقيقة200kΩ 0.1% | 1 | على التوالي مع MCP41HV51 لتوفير Rvar≈200–300kΩ | لم تحدد الشركة/المصدر | غير محسومة |
| TEN8-1222 | 1 | تحويل 12V إلى ±12V معزولين | TME/DigiKey دولي؛ لم يظهر محلياً | مرشح تغذية متوافق مع AD8336 |
| مرجع 1.65V + buffer | 1 | level-shift إلى ADC | لم يحدد رقم القطعة | غير محسوم |
| شبكة مقاومات matched 0.01% | حسب التصميم | differential subtraction/attenuator | لم تحدد القيم | غير محسومة |
| مكثفات C0G/NP0 ومكثفات decoupling | حسب التصميم | gyrator/filter/decoupling | محلياً متاح أنواع عامة؛ القيم لم تحسم | غير محسومة |

## 3. مرحلة TX

| القطعة | العدد المبدئي | الدور | التوفر | القرار |
|---|---:|---|---|---|
| IRFP264PBF 250V/38A | 1 | MOSFET TX، TO-247AC، RDS(on)75mΩ، Qg210nC | Power Lab يعرض IRFP264 بلا suffix؛ الأصالة/نسخة PBF غير مؤكدة؛ DigiKey يعرض PBF دولياً | مرشح أولي؛ لا شراء محلي دون إثبات suffix PBF/SOA |
| TC4420CPA | 1 | Gate driver | مرشح محلي؛ المخزون الدقيق يحتاج تأكيد | مرشح |
| شنت Kelvin 0.01Ω | 1 | قياس تيار TX | لم يحدد رقم القطعة/قدرة النبضة | غير محسوم |
| STTH112U | 1 | دايود سريع لفرع flyback | عرض محلي BinaryTech؛ يلزم تأكيد المصدر | مرشح فقط |
| 47Ω/20W | 1 | فرع flyback في النموذج | BinaryTech يعرض مقاومة bobbin؛ 380 دج/مخزون ظاهر10 | غير معتمدة؛ التحريض والـpulse overload غير مثبتين |
| 1.5KE39CA | 3 في نموذج الدراسة فقط | TVS string | Power Lab يعرض50 دج/قطعة ومخزون ظاهر | لا شراء؛ يلزم تدقيق الحرارة ومنحنى I-V |
| فيوز/حامل/مفتاح فصل | حسب التصميم | حماية طاقة | لم تحدد قيم نهائية | غير محسوم |
| حساس NTC | 2 مبدئياً | MOSFET والرأس | لم يحدد النوع | غير محسوم |

## 4. الرؤوس والميكانيك

| المجموعة | العدد | القرار |
|---|---:|---|
| Mono-loop head صغير | 1 | 20×20cm مربع،20 turns،0.60mm،pitch0.90mm،L≈181.9µH،R≈0.87Ω |
| Mono-loop head كبير | 1 | 35×35cm مربع،13 turns،0.60mm،pitch1.20mm،L≈175.8µH،R≈1.04Ω |
| كابل رأس shielded + موصل مقفل | 2 | Deutsch DT04-6P/DT06-6S، contacts13A؛ زوج قدرة1.5mm² + ID/NTC/AGND/shield |
| هيكل قابل للفك وحامل إلكترونيات | 1 | تصميم بعد أبعاد PCB والبطارية |
| بطارية 4S LiFePO4 12.8V 6Ah | 1 | BMS≥10A continuous و≥15A peak، شاحن14.6V؛ مصدر واحد لكل الجهاز |
| لوحة PCB مجمعة مصنعياً | 1–2 | بعد إغلاق schematic وDRC وBOM |
| علبة/مقبض/حزام | 1 | بعد تثبيت الوزن والأبعاد |

## 5. الموردون والروابط التي ظهرت

- TIKNO — ESP32-S3 N16R8 مع خيار لحام headers: https://tikno.edutech.dz/products/esp32-s3-n16r8-dual-core-ai-devkit-type-c
- Power Lab — فهرس MOSFET/TVS: https://powerlab.dz/product-category/composants-eletroniques/composants-actifs/
- BinaryTech DZ — مكونات/مقاومات: https://binarytech-dz.com/category/composants
- TRACO TEN8-1222: https://www.tme.com/ca/en/details/ten8-1222/dc-dc-converters/traco-power/ten-8-1222/
- Analog Devices AD8336: https://www.analog.com/en/products/ad8336.html
- TI OPA1612: https://www.ti.com/product/OPA1612
- ST NUCLEO-G474RE: https://www.st.com/en/evaluation-tools/nucleo-g474re.html

## 6. قواعد الشراء

1. لا نطلب شراء أي قطعة قبل إغلاق مخططها ومجال جهدها وتيارها وبدائلها.
2. القطع SMD/LFCSP تُركب من مصنع PCB؛ المستخدم لا يلحمها.
3. لا نشتري لوحة STM32 منفردة دون اعتمادها مع موصلات وخطة الطاقة والـfirmware.
4. لا نعتمد stock count من متجر وحده كدليل أصالة؛ يجب تأكيد الشركة/العلامة والدفعة.
5. نشتري حزمة متوافقة دفعة واحدة بعد إصدار BOM نهائية؛ لا قطع عشوائية أو زيادات.
6. لا نعد الجهاز مكتملاً قبل نجاح self-test المدمج والتحقق من waveform والحماية على منصة آمنة.

## 7. ما يمنع إصدار أمر الشراء حالياً

- VDCb وSWb وgyrator values لم تُحسم.
- مخطط الحماية النهائي للملف وAFE لم يغلق.
- clamp TX لم يُعتمد؛ TVS/مقاومة/دايود ما زالت فرضيات نموذج.
- قيم وأبعاد/لفات الرأسين لم تحسم.
- مخطط الطاقة وتوزيع الأرضي والـconnectors لم يغلق.
- لم تُراجع كل القطع معاً في schematic وBOM وPCB DRC.


## 8. تحديث هندسة الرأس والبطارية

أضيف ملف هندسة رأسين متناسقين حسابياً:
- Small: 20cm square,20 turns,0.60mm,pitch0.90mm,L≈181.9µH,R≈0.87Ω.
- Large: 35cm square,13 turns,0.60mm,pitch1.20mm,L≈175.8µH,R≈1.04Ω.
- طول النحاس الإجمالي للرأسين≈32.1m قبل أطراف التوصيل.

مصدر حساب المحاثة: Mohan et al. 1999.
https://web.stanford.edu/~boyd/papers/pdf/inductance_expressions.pdf

الطاقة المقترحة أصبحت بطارية واحدة 4S LiFePO4 12.8V/6Ah مع BMS≥10A مستمر و≥15A peak، وتغذي 5V MCU/ESP32 و±12V AFE وTX. Power Bank الموجود يبقى احتياطياً للاختبارات ولا يلزم في الوحدة النهائية.
