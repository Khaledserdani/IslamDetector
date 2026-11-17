# إسلام 2 — تدقيق تنفيذي لدائرة Bucking وتوصيل ADC على STM32G474RE
التاريخ: 2026-11-17
الفرع: hardware/islam-nextgen-final-platform
الحالة: تدقيق وثائقي؛ لا schematic نهائي ولا firmware ولا BOM.

## 1) تثبيت تفاصيل ورقة Bucking من النص المنشور
Kim et al. (2015), DOI 10.1049/el.2014.3895:
https://ietresearch.onlinelibrary.wiley.com/doi/10.1049/el.2014.3895

النص الكامل المتاح عبر فهرسة الناشر يوضح صراحة:
- النظام يتكون من search coil وTX وRX مع bucking circuit.
- TX والملف في النموذج المقترح مطابقان للمنظومة التقليدية؛ الاختلاف في المستقبل.
- bucking branch يتكون من SWb وVDCb ومحث ومقاومة على التوالي وVGA.
- الممانعة L وR تنفذ باستخدام gyrator يحول سعة الحمل C إلى محاثة محاكية.
- فصل تيار فرع المحاثة المحاكية بواسطة SWb يولد spike يتناقص أسيّاً.
- ثابت الزمن في وصف الورقة تحدده Rvar×C.
- أثناء المعايرة دون هدف، تضبط Rvar حتى يصبح Vout قريباً من الصفر، أي أن Vc يقارب جهد الملف الذاتي.
- عند وجود هدف، يبقى فرق استجابة الهدف بعد الطرح ليُضخّم.

هذا يثبت أن الفكرة الأصلية هي تعويض تناظري زمني قبل الكسب العالي، وليس معالجة رقمية بعد ADC.

## 2) بيانات القياس المنشور — من المصدر الأساسي
- ملف مربع حلزوني planar mono بمقاس 35×35 cm.
- L≈180 µH وRseries≈1.5 Ω.
- PCB FR-4 بسماكة 1.6 mm ونحاس 2 oz.
- مقاومة 350 Ω لتقليل ringing.
- TX MOSFET: IXTX32P60P.
- عرض نبضة التيار 300 µs؛ التكرار 1 kHz؛ جهد تغذية الملف 12 V.
- مضخمات النموذج تعمل بتغذية ±15 V.
- bucking: R=100 Ω وC=100 pF، وRvar بين 200 و300 kΩ.
- كسب المقارنة في النظام المقترح 1000 V/V (25×40).
- دون هدف، خرج التقليدي تشبع قرابة 50 µs بعد فصل التيار؛ bucking بقي دون التشبع.
- مع هدف M16 على بعد 15 cm، أصبحت استجابة التقليدي القابلة للاستخدام بعد نحو 100 µs، والمقترح بعد نحو 50 µs.
- عند جعل خرج الهواء متقارباً، قورنت منظومة تقليدية بكسب 150 V/V مع bucking بكسب 1000 V/V. أعطت الدراسة M15: 67 مقابل 89 cm، وM16: 49 مقابل 69 cm.

هذه قياسات الباحثين لأهدافهم وإعدادهم؛ ليست ضمان عمق ولا توقع أداء لإسلام. لا تنقل قيم R/C/350Ω أو MOSFET إلى تصميمنا قبل تحليل الممانعة والطاقة والتردد والتسامحات.

## 3) قيد مهم: المعادلة الأصلية للـgyrator
الناشر يعرض معادلة ممانعة gyrator كصورة رياضية، وليس نصاً قابلاً للاستخراج في نسخة الصفحة. لذلك لا نكتب قيمة L_eq أو معادلة Rvar من الذاكرة أو من topology مختلفة.
الخطوة الصحيحة: الحصول على شكل Fig.3 الأصلي بوضوح، ثم اشتقاق Z_in(s) من العقد الفعلية، والتحقق من وحدات المعادلة وحدود المضخم. لا تستخدم L_eq=R²C أو أي صيغة عامة قبل مطابقة الدارة الأصلية.
مرجع الورقة الذي استندت إليه دراسة Kim:
Jayalalitha & Susan, “Grounded simulated inductor – a review,” Middle-East Journal of Scientific Research, 15(2), 2013, DOI 10.5829/idosi.mejsr.2013.15.2.3706.

## 4) تصحيح اختيار ADC في STM32G474RE
مصادر ST الرسمية:
- Datasheet DS12288 Rev 6:
https://www.st.com/resource/en/datasheet/stm32g474re.pdf
- RM0440 Rev 9:
https://www.st.com/resource/en/reference_manual/dm00355726-stm32g4-series-advanced-armbased-32bit-mcus-stmicroelectronics.pdf
- AN5346:
https://www.st.com/content/st_com/en/technical-documents/an5346-stm32g4-adc-use-tips-and-recommendations-stmicroelectronics.html
- صفحة STM32G474RE:
https://www.st.com/en/microcontrollers-microprocessors/stm32g474re.html

### الحقائق المؤكدة
- STM32G474RE هو نسخة LQFP64 من STM32G474xE، وليس كل package في العائلة.
- خمسة ADCs بدقة 12-bit، مع معدل أقصى يصل إلى 4 MSPS في شروط مفردة؛ AN5346 يذكر حتى 3.46 MSPS في حالة multiple-ADC operation.
- ADC1/ADC2 يشكلان مجموعة ADC12، وADC3/ADC4/ADC5 مجموعة ADC345 مع مسارات clock/configuration مشتركة ضمن شروط العائلة.
- HRTIM ADC trigger 1 و3 متاحان كمصادر injected conversion على ADC3/4/5؛ يجب التحقق من جدول trigger selection في RM0440.
- لا يجوز افتراض أن ADC1/2 يقبلان HRTIM trigger 1/3 مباشرةً لمجرد وجود HRTIM.
- ADC triggers 5–10 لها routing مختلف؛ في RM0440 لكل trigger من هذه المجموعة اختيار مصدر واحد، ومجموعات 5/7/9 و6/8/10 تشترك في source sets.
- ST HAL/LL يوضح صراحة أن HRTIM injected triggers 1 و3 متاحة فقط على ADC3/4/5 في هذه العائلة.

### أثر ذلك على المعمارية
إذا كان المطلوب أخذ عينات RX بتوقيت HRTIM مباشر، فالمسار الأول المرشح هو ADC3/4/5، لا ADC1/2 تلقائياً.
لكن لا نختار ADC instance قبل:
1. اختيار pin فعلي متاح في LQFP64.
2. التأكد أن قناة ADC المطلوبة على هذا pin هي ADC3 أو ADC4 أو ADC5.
3. مراجعة trigger source المناسب (regular/injected) لذلك ADC.
4. مراجعة clock limits وsample time وsequence restrictions.
5. قياس معدل العينات الفعلي وDMA latency وnoise.

## 5) خطة توصيل أولية دون تثبيت pin
- RX bucking output: يذهب إلى قناة ADC3/4/5 على pin LQFP64 مثبت من جدول DS12288.
- TX current monitor: قناة ثانية، ويفضل أن تكون قابلة للقياس بتوقيت متزامن أو trigger منفصل، لكن لا نفرض ADC مزدوج قبل تحديد حاجته.
- monitor low-gain: optional channel إذا ثبت أن المسار الواحد لا يكفي لمراقبة clipping والـraw decay.
- ESP32-S3: لا يدخل في مسار ADC أو trigger؛ يتلقى buffers ونتائج عبر رابط رقمي مؤطر مع CRC/sequence.

## 6) اختبار firmware على NUCLEO-G474RE أو لوحة تقييم
قبل PCB مخصص:
1. إخراج HRTIM event إلى pin test/oscilloscope.
2. تشغيل ADC3/4/5 injected conversion على HRTIM trigger متاح.
3. تشغيل DMA/interrupt وتسجيل timestamp/sequence.
4. التحقق من phase delay بين event وحافة sample/conversion وفق إعدادات ADC.
5. اختبار overrun وjitter وفقد العينات عبر ملايين triggers.
6. مقارنة قناة واحدة ثم قناتين، لا البدء بخمس قنوات.
7. اختبار ADC مع source impedance مماثل لـAFE النهائي، لأن acquisition time يتأثر بمقاومة المصدر وسعة sample-and-hold.

## 7) قرار مرحلي
- Time-domain bucking يستحق prototype لأنه مثبت في ورقة PI فعلية مع تحسن recovery وgain.
- يجب محاكاة gyrator الأصلي من Fig.3، لا صيغة gyrator عامة.
- STM32G474RE ما زال مرشحاً عملياً، لكن مسار HRTIM-triggered ADC يرجح ADC3/4/5.
- لا pin assignment نهائي قبل رسم pin map كامل ومراجعة قيود الأرجل المشتركة.
- لا شراء أو BOM أو PCB في هذه المرحلة.

## 8) ما لم يتم بعد
- لم نحصل على نسخة واضحة من Fig.3/المعادلة الأصلية كصورة مستقلة.
- لم يتم اشتقاق transfer function للدائرة الأصلية.
- لم يتم إنشاء نموذج SPICE.
- لم يتم بناء firmware HRTIM+ADC.
- لم يتم قياس أي لوحة أو ملف لإسلام.
