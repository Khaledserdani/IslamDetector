# إسلام 2 — تدقيق مسار DAC3_CH2 + OPAMP3 + ADC3 على STM32G474RE LQFP64
التاريخ: 2026-11-17
الفرع: hardware/islam-nextgen-final-platform
الحالة: مسار توصيل مرشح موثق من داتا شيت ST وRM0440؛ ليس مخططاً نهائياً ولا اعتماد PCB.

## 1) نتيجة التدقيق: توجد سلسلة تناظرية/رقمية داخلية قابلة للتجربة
على STM32G474RE بحزمة LQFP64:
- PB2 هو الرجل 26، ويقدم OPAMP3_VINM.
- PB1 هو الرجل 25، ويقدم OPAMP3_VOUT وADC3_IN1.
- AN5306 يوضح أن OPAMP3 يمكنه اختيار DAC3_CH2 على دخله غير العاكس عند VP_SEL=11.
- يمكن توجيه OPAMP3 إلى خرج الرجل PB1 ثم قياسه بواسطة ADC3_IN1، أو استخدام مسار الخرج الداخلي إلى ADC3 channel 13 وفق RM0440/LL.
المراجع:
- DS12288 Rev 6: https://www.st.com/resource/en/datasheet/stm32g474re.pdf
- RM0440 Rev 9: https://www.st.com/resource/en/reference_manual/dm00355726.pdf
- AN5306 Rev 1: https://www.st.com/resource/en/application_note/dm00605707-operational-amplifier-opamp-usage-in-stm32g4-series-stmicroelectronics.pdf

## 2) المسار الأول المقترح للاختبار
DAC3_CH2 (قالب زمني) -> OPAMP3 non-inverting input
RX conditioning output -> PB2 / OPAMP3_VINM
OPAMP3 output -> PB1 / ADC3_IN1
ADC3 -> HRTIM injected trigger + DMA buffer

هذا التوصيل يستغل:
- DAC داخلي عالي السرعة دون رجل خرج DAC مستقلة.
- OPAMP3 بوصفه مرحلة analog reference/subtraction candidate.
- ADC3_IN1 كمدخل سريع خارجي، مع زناد HRTIM متاح لـADC3 حسب RM0440.
- PB1 وPB2 متاحان في LQFP64، ولا يحتاج هذا المسار إلى استعمال ADC1/2 لقياس الخرج.

## 3) معادلة أولية للطرح — بشرط دائرة التغذية الراجعة
إذا استُخدم OPAMP3 في تكوين مضخم عاكس مع مقاومة دخل Rin ومقاومة تغذية راجعة Rf، وكان دخل + هو VDAC:
Vout = (1 + Rf/Rin) × VDAC - (Rf/Rin) × VRX

عند Rf = Rin:
Vout = 2 × VDAC - VRX

لذلك إذا كان جهد RX المكيّف:
VRX = Vbias + Scoil
وكان قالب DAC:
VDAC = (Vbias + Stemplate) / 2
فإن:
Vout = Vbias + Stemplate - Scoil

وهكذا يظهر الفرق التناظري قبل ADC. هذه معادلة مثالية أولية؛ يجب إدخال سماحية المقاومات، مقاومة مصدر RX، offset وGBW وslew وقيود common-mode/output swing في التحليل. لا يعني ذلك أن الدارة جاهزة للتوصيل.

## 4) لماذا هذا المسار أفضل من مجرد DAC إلى رجل خارجية؟
- خرج DAC3_CH2 الداخلي يتصل مباشرة بمسار دخل OPAMP3 وفق multiplexer الداخلي.
- لا نحتاج إلى إخراج DAC عالي السرعة إلى رجل خارجية ثم إعادته عبر كابل أو مسار PCB طويل.
- يمكن أن يبقى الخرج التناظري محلياً وقصيراً، مع توجيه OPAMP3 إلى ADC3 مباشرة عبر الرجل PB1.
- إذا ثبتت جدوى مسار OPAMP3 internal output إلى ADC3 channel 13 مع HRTIM trigger، يمكن مقارنة هذا المسار الداخلي أيضاً؛ يجب الانتباه إلى متطلبات sample time الخاصة بخرج OPAMP.

## 5) حدود السرعة الحقيقية
الأرقام التي يجب عدم الخلط بينها:
- DAC الداخلي: معدل تحديث معلن حتى 15 MSPS.
- DAC+Comparator: أزمنة settling في جدول ST؛ وعند وجود OPAMP على خرج DAC تزداد أزمنة الاستقرار عن DAC وحده.
- OPAMP G4: GBW نموذجي نحو 13 MHz، وslew rate نموذجي نحو 45 V/µs في high-speed mode حسب AN5306.
- ADC: 4 MSPS أقصى معدل 12-bit في شروط مفردة محددة، وليس ضماناً لمعدل كامل مع DMA وقيود trigger والـAFE.
- HRTIM دقة توقيت عالية، لكنها لا تجعل ADC أو DAC أو OPAMP أسرع من حدوده الكهربائية.

يجب تحديد معدل اختبار مبدئي محافظ ثم رفعه تدريجياً، ومراقبة DAC underrun وADC overrun والـphase delay والـsettling.

## 6) قيد أساسي اكتُشف في داتا شيت DAC
الـDAC الداخلي 15MSPS unbuffered، وبياناته الكهربائية ليست مطابقة لخصائص DAC الخارجي buffered. يذكر جدول 76 settling مع OPAMP على خرج DAC، ويذكر جدول 77 دقة 15MSPS (ومنها حدود DNL/INL/TUE). لذلك:
- لا نعامل DAC على أنه مصدر مثالي.
- لا نحمل خرج DAC الداخلي خارجياً مباشرة.
- نستخدم مدخلاً داخلياً عالي الممانعة كما هو مقصود، ونتحقق من الاستقرار مع OPAMP.
- نختبر quantization/residual وspurs الناتجة من تحديث DAC.

## 7) أهم خطر علمي: احتمال طرح إشارة الهدف
القالب لا يُستخرج ويُحدّث تلقائياً أثناء الكشف. سياسة الاختبار:
1. تسجيل raw RX قبل الإلغاء.
2. معايرة القالب على منطقة مرجعية خالية من الأهداف.
3. حفظ نسخة القالب ودرجة الحرارة وجهد TX.
4. عند وجود anomaly أو residual فوق حد الاشتباه، تجميد تحديث القالب.
5. مقارنة residual مع raw signal، وقياس نسبة بقاء استجابة الهدف.
6. تشغيل الاختبارات دون قالب وبقالب ثابت وبقالب متكيف منفصلين.

## 8) اختبارات القبول قبل أي اختيار
A. DAC3_CH2 وحده: ramp وstep وexponential-template، قياس الشكل/التوقيت/الضجيج.
B. OPAMP3: قياس offset وgain وsettling وclipping وrecovery.
C. ADC3: قياس trigger-to-sample latency وDMA sequence integrity.
D. analog subtraction: مقاومات matched، قياس residual دون هدف ثم مع هدف معياري.
E. robustness: تغير VDDA والحرارة وRcoil والكابل والارتفاع، ثم إعادة القياس.
F. مقارنة baseline PI وGyrator وDAC-template بنفس ظروف القياس.

معايير النجاح:
- residual أقل بوضوح من baseline ضمن نافذة القياس المستهدفة.
- بقاء استجابة الهدف أعلى من حد SNR محدد مسبقاً.
- عدم حدوث clipping أو recovery بطيء أو DMA underrun/ADC overrun.
- استقرار المعايرة مع الحرارة والجهد وتكرار sweeps.

## 9) القرار المرحلي
هذا المسار مرشح قوي لاختبار منضدة، لأن route الأساسي يمكن أن يكون:
DAC3_CH2 -> OPAMP3 -> PB1/ADC3_IN1، مع RX يدخل من PB2.
لكن لا نثبّت pinout النهائي حتى نراجع كل وظائف PB1/PB2 وتعارضاتها مع واجهات الاتصال والـdebug وHRTIM، ولا نثبت القيم قبل اشتقاق الدارة والحماية.

## 10) ما لم يتم
- لا schematic نهائي.
- لا SPICE simulation منفذة.
- لا firmware HRTIM/DAC/ADC منفذ.
- لا قياس عتادي أو waveform capture.
- لا BOM ولا PCB.
- لا ادعاء أداء أو عمق كشف.


## 11) تدقيق دقة القالب وحدود إلغاء الـDAC
تظهر داتا شيت DS12288 Rev 6 في جدول 77 لقنوات DAC 15MSPS:
- DNL ضمن ±2 LSB.
- INL ضمن ±5 LSB.
- TUE ضمن ±5 LSB.
- مواصفات settling تتغير بحسب وجود comparator وOPAMP على خرج DAC وبحسب VDDA.
- يذكر جدول 76 أزمنة settling عند توصيل OPAMP على خرج DAC؛ لذلك لا يجوز مساواة معدل تحديث DAC بزمن استقرار المسار النهائي.

أثر ذلك على معادلة الطرح عند Rf/Rin=1:
- كل خطوة DAC مقدارها 1 LSB تنتج نظرياً خطوتين في Vout بسبب معامل 2.
- أي offset/gain error أو عدم تطابق مقاومات يترك residual حتى في غياب الهدف.
- لا يكفي أن يبدو المنحنى متشابهاً على الشاشة؛ يجب قياس residual بوحدات الجهد وRMS/SNR.

استراتيجية تخفيف الخطأ المقترحة:
1. قياس transfer curve للـDAC3_CH2 عبر مسار OPAMP3/ADC3 على عدة نقاط، مع معايرة ADC أولاً.
2. حفظ جدول تصحيح ثابت لكل لوحة/شريحة إذا كانت الأخطاء مستقرة.
3. إجراء معايرة offset/gain للمسار التناظري بعد التجميع.
4. قياس الخطأ الديناميكي عند معدلات تحديث متعددة، لا الاكتفاء بقياس DC.
5. اختبار تأثير DNL وspikes عند هبوط الكود، وخصوصاً عند القفزات الكبيرة في القالب.
6. اعتماد معيار قبول residual قبل/بعد المعايرة؛ إذا بقيت أخطاء DAC/OPAMP أعلى من إشارة الهدف في نافذة الكشف، يسقط هذا المسار مهما كانت سرعته الاسمية.

حساب توضيحي فقط: عند VREF+=3.3V، خطوة DAC النظرية 3.3/4096≈0.806mV. في صيغة Vout=2×VDAC−VRX يصبح أثر خطوة DAC الواحدة على الخرج النظري ≈1.61mV. هذا قبل أخطاء DAC والـOPAMP والمقاومات والضجيج. يجب إعادة الحساب بجهد المرجع الحقيقي وقياس transfer curve للقطعة الفعلية.
