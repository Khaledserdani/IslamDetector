# تدقيق أرجل STM32G474RE LQFP64 ومسار القياس — إسلام 2
التاريخ: 2026-11-17
الفرع: hardware/islam-nextgen-final-platform

## 1. الهدف
تحويل اختيار STM32G474RE من ترشيح عام إلى تدقيق package-aware قبل رسم PCB. هذه الوثيقة لا تعتمد pinout نهائياً؛ إنها تسجل القنوات التي تثبتها الداتا شيت وتحدد ما يلزم قبل تثبيت التوصيل.

## 2. حقائق مؤكدة من ST DS12288 Rev 6
- STM32G474RE هو إصدار xE، وحزمة R هي LQFP64.
- العائلة تتضمن خمسة ADCs بدقة 12-bit؛ لكن لا يجوز افتراض أن كل قناة داخلية/خارجية متاحة على كل package.
- الذاكرة: 96 KB SRAM عامة + 32 KB CCM SRAM؛ لا تعامل CCM كذاكرة DMA عامة.
- الداتا شيت تعرض قنوات ADC لكل رجل في Table 12، وأرقام أرجل LQFP64 في العمود المخصص للحزمة.

المصدر الرسمي:
https://www.st.com/resource/en/datasheet/stm32g474re.pdf

## 3. مداخل ADC3 المتاحة فعلياً على LQFP64
| الرجل | رقم رجل LQFP64 | قناة ADC |
|---|---:|---|
| PB0 | 24 | ADC3_IN12 (ومشترك ADC1_IN15) |
| PB1 | 25 | ADC3_IN1 (ومشترك ADC1_IN12) |
| PE7 | 53 | ADC3_IN4 |
| PE9 | 55 | ADC3_IN2 |
| PE13 | 59 | ADC3_IN3 |
| PB13 | 44 | ADC3_IN5 |

هذه خيارات حقيقية ظاهرة في جدول Table 12. لا تعني أن كل القنوات يمكن تشغيلها في simultaneous/injected mode بلا قيود، ولا أن كل trigger يمكن ربطه بكل ADC.

## 4. مداخل ADC4 المتاحة التي ظهرت في جدول الأرجل
| الرجل | رقم رجل LQFP64 | قناة ADC |
|---|---:|---|
| PB12 | 43 | ADC4_IN3 (ومشترك ADC1_IN11) |
| PB14 | 45 | ADC4_IN4 (ومشترك ADC1_IN5) |
| PB15 | 37 | ADC4_IN5 (ومشترك ADC2_IN15) |
| PE14 | 60 | ADC4 channel mapping مدرج في Table 12 ويجب تدقيق suffix/channel كامل قبل الاعتماد |
| PE15 | 38 | ADC4_IN2 |

ملاحظة: لا نستخدم PE14 كمدخل ADC في المخطط قبل استخراج رقم القناة الصحيح من السطر الأصلي؛ صيغة النص المستخرج آلياً في الداتا شيت غير واضحة عند هذا الموضع.

## 5. خطة توزيع أولية — غير مثبتة
- قناة قياس رئيسية: نختارها من ADC3 بعد مراجعة trigger وsampling time.
- قناة ثانية اختيارية: ADC4 لمراقبة تيار TX أو مرجع bucking، إذا كان التزامن المطلوب مدعوماً فعلاً.
- قناة مراقبة بطيئة: قياس البطارية/حرارة اللوحة أو مرجع ADC، لا تستهلك قناة عالية السرعة دون ضرورة.
- لا نحجز أرجل HRTIM output أو fault input قبل مطابقة pin alternate functions مع جدول HRTIM في RM0440.
- نحتفظ بإمكانية bypass لدائرة bucking حتى نستطيع مقارنة PI baseline وPI+bucking دون تغيير لوحة القياس.

## 6. ما لم يغلق بعد
1. جدول JEXTSEL وtrigger source لكل ADC مطلوب، بما في ذلك أي trigger HRTIM فعلي يختار.
2. إثبات simultaneous sampling أو توقيت ADC3/ADC4 بالنسبة إلى الحدث نفسه، مع قيود injected/regular groups.
3. مطابقة DMA request mapping وذاكرة buffer؛ لا توضع buffers في CCM إذا كان DMA لا يستطيع الوصول إليها.
4. التحقق من الأرجل المستخدمة فعلاً على لوحة NUCLEO-G474RE إن كانت ستستخدم كنموذج أولي، وعدم افتراض أن كل أرجل MCU مكشوفة أو غير محجوزة.
5. فحص analog input source impedance، sampling capacitor، sampling time، مرشح RC، حماية clamp، ووقت الاستقرار بعد switching.
6. لا يصدر pinout نهائي ولا PCB حتى تُغلق البنود أعلاه.

## 7. قرار التنفيذ
- STM32G474RE يبقى مرشحاً قوياً ولا يوجد حالياً سبب علمي لإسقاطه.
- لا تثبيت نهائي للأرجل حتى يكتمل RM0440 routing وDMA audit.
- الخطوة التالية هي إنشاء جدول pin/ADC/trigger/DMA موحد، ثم مراجعة schematic block-level. لا توجد محاكاة أو قياسات عتادية مزعومة في هذه الوثيقة.

## 8. المراجع
1. ST DS12288 Rev 6, Table 12 and LQFP64 pinout, especially pages 50 and 58–63:
https://www.st.com/resource/en/datasheet/stm32g474re.pdf
2. ST RM0440:
https://www.st.com/resource/en/reference_manual/dm00355726-stm32g4-series-advanced-armbased-32bit-mcus-stmicroelectronics.pdf
3. ST NUCLEO-G474RE ADC example:
https://github.com/STMicroelectronics/STM32CubeG4/blob/master/Projects/NUCLEO-G474RE/Examples_MIX/ADC/ADC_SingleConversion_TriggerSW_IT/ADC_SingleConversion_TriggerSW_IT.ioc
