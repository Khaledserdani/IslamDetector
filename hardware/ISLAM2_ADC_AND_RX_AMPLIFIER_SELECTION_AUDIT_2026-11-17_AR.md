# إسلام 2 — تدقيق اختيار ADC ومضخم الاستقبال بعد مراجعة أوراق البيانات
التاريخ: 2026-11-17
الفرع: hardware/islam-nextgen-final-platform
الحالة: قرار معماري مرحلي؛ لا اعتماد شراء.

## 1) النتيجة المختصرة
لا نشتري ADC خارجياً الآن. نبني أول منصة قياس حول STM32G474RE ونختبر ADC الداخلي مع HRTIM وDMA بعد أن نتحقق من تزامن القنوات والـpackage والـclock. نترك footprint/واجهة اختيارية لـADC خارجي إذا أثبتت القياسات نقصاً في الدقة أو الضجيج أو القنوات المتزامنة.

السبب: ADC خارجي 18-bit لا يعوض front-end مشبعاً، ولا يضمن SNR فعلياً في transient، وقد يزيد الطاقة والكلفة وتعقيد SPI والمرجع واللوحة.

## 2) STM32G474RE كخط أساس
صفحة ST الرسمية تؤكد للعائلة:
- خمسة ADCs سريعة 12-bit، حتى 4 MSPS في ظروف التشغيل المحددة.
- 3.46 MSPS كحد مذكور عند التشغيل متعدد ADC وفق AN5346.
- HRTIM بدقة توقيت 184 ps ومصادر زناد ADC داخلية.
- RM0440 يصف تزامن injected conversions لبعض أزواج ADC، ويذكر شروط تساوي طول sequences وعدم تكرار نفس القناة على ADCين متزامنين.

الاستنتاج:
- فترة 4 MSPS النظرية 250 ns، لكنها ليست ضماناً أن كل محولات STM32G474RE تعمل معاً بهذا المعدل.
- يجب تثبيت القنوات/الأزواج بناء على جدول الأرجل في datasheet الخاص بالنسخة RE، وليس اعتماد عدد ADCs العام للعائلة.
- نستخدم HRTIM للـTX event وblanking وADC triggers، وDMA لجمع buffers دون polling برمجي.
- نختبر 1 أو 2 قنوات متزامنة أولاً. لا نحتاج خمس قنوات في أول prototype إلا إذا أثبتت تجربة MR أو current sensing الحاجة.

## 3) AD4003 كمرشح خارجي وليس اختياراً حالياً
الخصائص الرسمية:
- SAR differential ADC بدقة 18-bit وthroughput حتى 2 MSPS.
- لا pipeline latency، وميزة high-Z mode/long acquisition phase لتخفيف متطلبات driver في ظروف معينة.
- SNR نموذجي 100.5 dB عند 1 kHz، ولا يجوز إسقاط هذا الرقم على transient أو ترددات/دوائر أخرى.
- يحتاج مرجعاً خارجياً وواجهة SPI سريعة وتصميماً دقيقاً لمدخل differential والـreference.
- input clamp الداخلي مذكور لتحمل تيار clamp حتى 50mA؛ هذا ليس حماية كافية لنبضة ملف بحث ولا يغني عن حماية AFE خارجية محسوبة.

التقييم:
- مناسب كمرشح لقناة precision لقياس residual بعد bucking أو قياسات بطيئة/مقارنة.
- لا يتفوق تلقائياً على ADC الداخلي لالتقاط أول transient: معدل 2MSPS أقل من 4MSPS النظري للـSTM32، وإن كان يملك دقة اسمية أعلى.
- قد يكون مفيداً إذا أثبت اختبار ADC الداخلي أن ENOB/الضجيج/الخطية غير كافية بعد تخفيض الإشارة وإزالة التشبع.
- لا يوضع قبل bucking أو حماية RX.

## 4) OPA828 — أين يصلح وأين لا؟
تذكر TI:
- ضجيج دخل 4 nV/√Hz عند 1 kHz.
- GBW نحو 45 MHz.
- Slew rate نحو 150 V/µs.
- settling time 120 ns إلى 14-bit وفق شروط القياس المحددة في ورقة البيانات.
- تغذية واسعة ±4 إلى ±18V، وليس مضخماً rail-to-rail يعمل مباشرة على 3.3V.

الاستنتاج:
- أرقام الضجيج والسرعة تجعله مرشحاً لمرحلة كسب لاحقة بعد أن تخف الإشارة الذاتية الكبيرة.
- لا نعتمده كأول مرحلة RX تتعرض مباشرة إلى نبضة الاقتران؛ settling time المحدد ليس دليلاً على overload recovery بعد التشبع.
- لا نعتمد 120ns كزمن استعادة بعد نبضة TX. يجب قياس overload recovery الفعلي في الدارة، أو اختيار مضخم لديه مواصفة/بيانات recovery مناسبة.
- يحتاج rails مناسبة وتحقق استقرار مع شبكة bucking والـADC؛ هذا يرفع التعقيد والطاقة.

## 5) ترتيب سلسلة القياس الموصى به للاختبار
ملف RX
 -> حماية/تخميد منخفضة السعة محسوبة
 -> نقطة مراقبة منخفضة الكسب
 -> time-domain bucking / طرح مرجع ذاتي
 -> كسب أولي معتدل
 -> كسب لاحق قابل للضبط
 -> مرشح anti-alias محسوب
 -> ADC الداخلي STM32G474RE (الخط الأول)
 -> DMA buffer + timestamp

مسار قياس مستقل لتيار TX:
shunt أو current sensor محسوب + amplifier/ADC مناسب، مع عزل مسارات التيار العالي عن أرضي AFE.

مسار ADC خارجي اختياري:
يضاف فقط على لوحة تقييم أو daughterboard بعد نجاح bucking، ويقارن مباشرة مع ADC الداخلي على نفس الإشارة.

## 6) اختبار المفاضلة المطلوب
استخدم signal source أو waveform injection معلوم، ثم اختبار الملف على طاقة منخفضة:
1. ADC الداخلي: قياس noise floor وSNR وENOB تقريبياً عند معدلات sampling المختلفة.
2. ADC الخارجي AD4003: نفس الإشارة ونفس bandwidth ونفس front-end، مع تعويض اختلاف gain/reference.
3. قياس settling/latency وفقد البيانات وCPU/DMA/SPI load.
4. قياس الأداء مع bucking ومن دونه.
5. اختبار تغير common-mode وحرارة اللوحة.
6. اختبار clipping وoverload recovery في المضخم قبل ADC.

لا تعلن فوز ADC بناء على عدد البتات الاسمي. الفائز هو من يعطي أقل uncertainty في القياس الفعلي ضمن bandwidth والنافذة الزمنية المطلوبة وبأقل تعقيد وطاقة.

## 7) قرارات هذه الجولة
- STM32G474RE: يبقى المرشح الرئيسي للتحكم والتوقيت وADC أولي.
- ADC الداخلي: baseline mandatory للتجربة الأولى.
- AD4003: optional precision ADC candidate؛ لا شراء قبل اختبار داخلي.
- OPA828: candidate لمرحلة كسب لاحقة فقط؛ ليس اختيار first-stage RX.
- ADS8688: ليس ADC المسار السريع early-time؛ يمكن إعادة تقييمه لقنوات مراقبة بطيئة إذا احتجنا ذلك.
- لا BOM ولا شراء ولا مخطط نهائي بعد.

## 8) مصادر أولية
1. ST STM32G474RE official product page:
https://www.st.com/en/microcontrollers-microprocessors/stm32g474re.html
2. ST RM0440 Rev 9:
https://www.st.com/resource/en/reference_manual/dm00355726-stm32g4-series-advanced-arm-based-32bit-mcus-stmicroelectronics.pdf
3. ST AN5346 — STM32G4 ADC use tips and recommendations:
https://www.st.com/content/st_com/en/technical-documents/an5346-stm32g4-adc-use-tips-and-recommendations-stmicroelectronics.html
4. Analog Devices AD4003 datasheet:
https://www.analog.com/media/en/technical-documentation/data-sheets/AD4003-4007-4011.pdf
5. TI OPA828 datasheet:
https://www.ti.com/lit/ds/symlink/opa828.pdf

## 9) ما لم يثبت بعد
- لم نقس ENOB أو SNR على لوحة إسلام.
- لم نثبت ADC pin mapping والتزامن للنسخة الدقيقة من package.
- لم نقس overload recovery لأي مضخم مع ملف TX.
- لم يُختبر AD4003 على prototype إسلام.
- لا توجد نتائج عتادية أو اعتماد شراء.
