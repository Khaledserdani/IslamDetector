# تصميم AFE الأساسي — Time-domain bucking + Differential receiver

التاريخ: 2026-11-14
الفرع: hardware/islam-nextgen-final-platform
الحالة: مواصفة كتلية ومكونات مرشحة؛ ليست schematic نهائية.

## 1. القرار الوظيفي

نستخدم بنية الدراسة المنشورة، مع تغذية تناظرية مستقلة يحدد جهدها بعد المحاكاة، ثم مرحلة خرج آمنة ومكيّفة إلى ADC بمرجع 3.3V:
1. دخل الملف مع حماية نبضية عالية السرعة.
2. تضخيم أولي مستقل لإشارة الملف.
3. مرجع bucking تناظري يولد اضمحلالاً قابلاً للضبط.
4. تضخيم مرجع bucking بمقياس مماثل لمسار الملف.
5. Differential amplifier يطرح المرجع من إشارة الملف قبل الكسب النهائي.
6. خرج centered عند 1.65V ومحدود ضمن مجال ADC.
7. قناة مراقبة ثانية من المرجع/الإشارة الخام إلى ADC2.

الهدف الحفاظ على الإشارة قبل ADC ومنع التشبع في المراحل التناظرية، وليس مجرد زيادة دقة التحويل.

## 2. مكونات مرشحة للمسار التناظري

### OPA2365 — مرشح سابق غير معتمد
TI تصنف OPA2365 Active وتذكر:
- تغذية 2.2–5.5V (مناسب لـ3.3V).
- GBW=50MHz.
- Slew rate=25V/µs.
- ضجيج 4.5nV/√Hz.
- Rail-to-rail input/output.
- Settling نحو0.3µs إلى0.01%.
- Offset أقصى 0.2mV.
- CMRR حد أدنى100dB.

هذه المواصفات لا تكفي وحدها لإثبات صلاحيته لمخطط bucking الكامل. بعد مراجعة الدراسة الأصلية، لا نعتمد تشغيل AFE على 3.3V ولا نعتمد OPA2365 أساساً؛ يبقى مرشحاً تجريبياً فقط إذا أثبتت محاكاة headroom وsettling والحماية صلاحيته.

المصدر:
https://www.ti.com/product/OPA2365
https://www.ti.com/lit/ds/symlink/opa2365.pdf

### AD8421 — خيار بديل ممتاز إذا احتجنا Instrumentation Amp
AD8421 يقدم 3.2nV/√Hz، 10MHz عند G=1، 2MHz عند G=100، settling 0.6µs إلى0.001% عند G=10، وحماية مدخل إلى40V من rail المقابل، وتغذية 5–36V مفردة أو ±2.5 إلى±18V. لكنه ليس مثبت التوفر محلياً، ويتطلب تغذية5V على الأقل.

يبقى خياراً بديلاً إذا أثبتت محاكاة headroom وsettling وCMRR ملاءمته. لا توجد أفضلية نهائية مثبتة بينه وبين OPA1612 حتى إغلاق نموذج AFE.

المصدر:
https://www.analog.com/media/en/technical-documentation/data-sheets/ad8421.pdf

## 3. تقسيم القنوات المقترح

تصور سابق غير معتمد باستخدام OPA2365 (يُحتفظ به للمقارنة فقط):
- U1A: مضخم أولي لمسار الملف، كسب مرجعي أولي25.
- U1B: gyrator/محاكاة المحث لمسار bucking.
- U2A: buffer/كسب مرجع bucking بحيث يطابق مسار الملف.
- U2B: differential stage، كسب مرجعي أولي40، مع شبكة مقاومات matched 0.01% أو أفضل.

الكسب الكلي النظري المرجعي = 25×40=1000. لا نعتمده قبل حساب headroom والضجيج وsettling؛ يمكن خفض الكسب أو تغييره بحسب شكل الإشارة.

ADC1 يقرأ خرج الفرق الأساسي. ADC2 يراقب مرجع bucking أو خرج المسار الخام بعد تكييف آمن.

## 4. ضبط مرجع bucking ومفتاحه

مرجع الدراسة:
- C=100pF.
- Rvar=200–300kΩ.
- τ=Rvar×C≈20–30µs.
- R ثابت في شبكة gyrator=100Ω.
- التحكم بالسعة عبر VGA، ويمكن أن يضبط DAC1_CH1 نقطة التحكم في VGA بعد تحديد نوعها.

تنفيذ رقمي مرشح بعد تثبيت gyrator:
- مكثف C0G/NP0 بقيمة100pF وتفاوت1% أو أفضل.
- مقاومة ثابتة200kΩ دقيقة (0.1% مبدئياً).
- MCP41HV51-104E/ST: مقاومة رقمية100kΩ، 8-bit، 256 taps، SPI، حزمةTSSOP-14.
- التغذية التناظرية للمقاومة الرقمية: V+=+12V_AFE وV−=−12V_AFE، وDGND=AGND؛ التغذية الرقمية VL=3.3V، ومتوافقة مع SPI في STM32. أطراف A/B/W تتحمل مجالاً يصل إلى±18V، لذا لا تتجاوز rails.
- المجال الاسمي مع200kΩ ثابتة: Rvar≈200–300kΩ. خطوة المقاومة≈392Ω، وخطوة τ≈0.039µs عند C=100pF.
- تيار طرفي MCP41HV51 الأقصى لنسخة100kΩ نحو6.5mA؛ تيار gyrator المتوقع أقل بكثير.
- تحكم SPI من STM32G474 عبر PB13/PB15 وCS على PB6.
- DAC1_CH1/CH2 يتحكمان في AD8336 VGA عبر attenuator/RC، وليس بديلاً عن VDCb أو SWb.
- HRTIM يطلق SWb نسبةً إلى TX-off.
- firmware يكتب قيمة wiper بعد استقرار ±12V و3.3V؛ لا يعتمد على POR code. تُحفظ قيمة المعايرة في Flash.

**تسلسل الطاقة:** يدعم الجهاز إقلاع التغذية التناظرية أو الرقمية أولاً؛ المهم أن يكون DGND مرجعاً مشتركاً بين المجالين، وألا يرتفع DGND فوق V+ أثناء الإقلاع. يبقى CS غير فعال أثناء startup. يربط WLAT إلى DGND (منخفض) لأننا لا نحتاج تحديثاً متزامناً، ويربط SHDN إلى VL عبر10kΩ (غير فعال).

المصادر:
https://www.microchip.com/en-us/product/MCP41HV51
https://ww1.microchip.com/downloads/aemDocuments/documents/MSLD/ProductDocuments/DataSheets/MCP41HVX1-Data-Sheet-20005207.pdf

## 5. حماية مدخل AFE

الملف قد يشهد جهداً عابراً أعلى بكثير من مجال3.3V. لذلك:
- مقاومة سلسلة نبضية تحد تيار مدخل الحماية.
- مشابك منخفضة السعة/التسريب إلى مرجع AFE، لا إلى رجل MCU مباشرة.
- مرجع clamp له مكثف reservoir ومسار تفريغ حتى لا يرتفع rail بسبب تيار النبضة.
- لا يُسمح لمدخل OPA2365 أو ADC بتجاوز حدود absolute maximum.
- يجب أن يبقى clamp خارج مسار الإشارة الصغيرة بعد زوال transient، بحيث لا يخفض الإشارة الهدف.
- قيمة مقاومة السلسلة ونوع الدايود يحددان بعد حساب جهد الملف الأقصى ومدة النبضة وشحنة clamp. لا نعتمد 1kΩ أو 470Ω الآن كقيمة نهائية.

## 6. المرجع والـlayout

- مرجع midscale=1.65V منخفض الضجيج، مشترك بين مراحل AFE ومسار ADC بعد buffer.
- فصل أرضي القدرة النبضية عن أرضي AFE، مع نقطة اتصال محسوبة واحدة.
- مسارات الملف/القدرة قصيرة وبعيدة عن مدخل AFE.
- زوج تفاضلي قصير بين preamp وdifference stage.
- مكثفات decoupling 100nF عند كل IC مع bulk محلي.
- لا تمرر TX gate أو drain تحت AFE أو ADC.
- مقاومات الفرق من شبكة matched واحدة، لا أربع مقاومات عشوائية.

## 7. قرار الحالة

- **المرشح الأساسي قيد إعادة التصميم:** OPA1612 مع تغذية تناظرية منفصلة، gyrator حقيقي، VGA، وطرح تفاضلي. لا توجد قيم نهائية بعد.
- **خيار بديل:** AD8421 كـinstrumentation amplifier إذا تطلب القياس CMRR/ضجيجاً أعلى، بعد تأكيد تغذيته وتوريده.
- **غير معتمد بعد:** قيم الكسب النهائية، مقاومة دخل AFE، دايودات الحماية، مصدر 1.65V، نوع/قيمة LDO، وعدد نوافذ العينة.
- **لا شراء:** لا تشتري OPA2365 أو MCP41HV51 منفردين قبل تجميع BOM النهائي؛ القطع SMD ستأتي على لوحة مجمعة مصنعياً.



## 8. حماية/Blanking بمسارين بدل تعريض الكسب العالي للنبضة

ظهر أثناء مراجعة مجال الجهد أن توصيل preamp بكسب25 مباشرة إلى عقدة الملف طوال TX قد يشبعه قبل أن يتمكن bucking من المساعدة. لذلك نضيف بنية dual-path:
- **مسار مراقبة منخفض الكسب ومحمي** يبقى متصلاً، ويقيس envelope بعد مقاومة سلسلة ومشابك منخفضة السعة.
- **مسار كسب عالٍ** يبقى مفصولاً خلال TX والـflyback، ثم يوصل بعد أن يؤكد comparator أن الإشارة هبطت إلى مجال آمن.
- بعد التوصيل، يطرح bucking المرجع من إشارة الملف، ثم يطبق الكسب العالي.
- ADC2 يراقب المسار المنخفض/مرجع bucking؛ ADC1 يقرأ خرج الفرق عالي الكسب.

هذا لا يستبدل bucking؛ بل يمنع تشبع المرحلة الأولى قبل أن يصل الفرق إلى مرحلة الطرح.

### مرشح analog switch — تم استبدال TMUX1134
**TMUX6219** من TI:
- قناة واحدة SPDT لكل شريحة.
- تغذية مزدوجة ±4.5V إلى±18V، مناسبة لـ±12V_AFE.
- RON نموذجي2.1Ω.
- Charge injection نحو−10pC.
- bandwidth43MHz.
- تيار مستمر حتى330mA في حزمة VSSOP.
- منطق تحكم1.8V متوافق مع GPIO/HRTIM 3.3V.
- Break-before-make وfail-safe logic.

يستخدم شريحتان: الأولى لـSWb والثانية لـhigh-gain blanking. يمرر إشارات ثنائية القطبية ضمن rails، لكنه لا يوصل مباشرة بعقدة flyback خارج ±12V.

المصدر:
https://www.ti.com/product/TMUX6219
https://www.ti.com/lit/ds/symlink/tmux6219.pdf

### حماية دخل منخفضة السعة
**BAV99** dual switching diode مرشح محلي لحماية عقدة AFE بعد مقاومة سلسلة:
- لا نعتمد توصيل clamp إلى 3.3V_AFE مباشرة. أي clamp rail يحتاج حساب تيار الحقن ومسار امتصاص مستقل قبل اعتماده.
- صفحة Power Lab تعرض BAV99 بسعر15 دج ومخزون ظاهر5890 وقت الفهرسة.
- قيمة مقاومة السلسلة ونوع clamp لم يحسما بعد؛ لا تعتمد قيمة1kΩ من الحساب النظري السابق.
- أي clamp إلى rail يحتاج مسار امتصاص/bleeder محسوباً، ولا يحقن تياراً غير مسموح في3.3V أو±12V.
- لا يصل clamp مباشرة إلى رجل MCU؛ يكون على لوحة AFE قبل buffer/analog switch.

المصدر:
https://powerlab.dz/product/bav99-dual-series-switching-diode-sot-23/

## 9. كشف التعافي عتادياً باستخدام COMP/HRTIM

تم التحقق من RM0440 أن STM32G474 يستطيع ربط مخارج COMP داخلياً بمداخل HRTIM external events وfault inputs، وأن DAC3_CH1/CH2 داخليان ويمكنهما ضبط عتبات COMP1/COMP2:
- COMP1: PB1 كمدخل موجب لقياس shunt تيار TX، وDAC3_CH1 كعتبة؛ خرجه يوقف HRTIM عبر fault عند overcurrent.
- COMP2: PA7 كمدخل موجب لمسار envelope منخفض الكسب، وDAC3_CH2 كعتبة recovery؛ خرجه يطلق HRTIM event عند وصول الإشارة إلى المجال الآمن.
- PA12 يبقى interlock/إيقاف خارجي إضافي.
- HRTIM يفرض minimum delay ثم يفتح TMUX6219 للمسار عالي الكسب. إذا لم يصل recovery قبل timeout، يمنع النبضة التالية.

هذا يوفر استجابة عتادية لا تعتمد على polling أو Wi-Fi. القيم الرقمية للعتبات والـhysteresis تُحدد بعد محاكاة/قياس الإشارة.

المصدر:
https://www.st.com/resource/en/reference_manual/dm00355726.pdf
https://www.st.com/resource/en/user_manual/dm00556337.pdf

## 10. تحديث مكونات AFE المرجحة

- OPA1612 ×2 (مرشح أولي فقط): preamp/gyrator/differential stages بعد حساب التغذية والكسب؛ لا شراء قبل المحاكاة.
- TMUX6219 ×2: blanking/enable high-gain path بعد clamp.
- BAV99: مرشح حماية بحثي فقط، غير معتمد ولا يوصل مباشرة إلى rails.
- MCP41HV51 ×1: ضبط Rvar 200–300kΩ عبر 200k ثابت +100k digital pot.
- C0G 100pF، R=100Ω، وشبكة مقاومات matched 0.01% أو أفضل.
- DAC1_CH1/PA4 يضبط bucking amplitude.
- DAC3_CH1/CH2 داخليان لعتبات COMP1/2.
- ADC1/ADC2 متزامنان على PA0/PA1.
- SPI2 PB13/PB15 وCS PB6 للمقاومة الرقمية.

لا تزال هذه قائمة مرشحين وليست BOM شراء نهائية؛ يلزم التحقق من headroom والضجيج وsettling وabsolute maximum لكل عقدة.


## 11. تصحيح معماري بعد قراءة النص الكامل والـPDF الأصلي للدراسة

هذا القسم يعلو على أي صياغة سابقة متعارضة في هذا الملف.

### 11.1 البنية الصحيحة لمولد bucking

الدراسة لا تصف مجرد DAC يحقن منحنى اصطناعياً، بل فرعاً مستقلاً يتكون من:
- مصدر DC مستقل (V_{DCb}).
- مفتاح bucking مستقل (SW_b).
- شبكة gyrator تمثل محثاً ومقاومة على التوالي.
- VGA يضبط سعة الإشارة المرجعية.
- Differential amplifier يطرح الإشارة المرجعية المكبرة من إشارة الملف المكبرة.

المحث المكافئ في الدراسة:
[
L_{var}=R_{var}RC
]
والثابت الزمني:
[
\tau_b=R_{var}C
]
بالقيم المرجعية R=100Ω وC=100pF وRvar=200–300kΩ:
- (L_{var}=2–3mH).
- (	au_b=20–30µs).

عند إطفاء SWb يتولد spike ثم اضمحلال أسي، ويضبط Rvar ثابت الزمن. وتضبط VGA سعة المرجع لتقارب سعة اضمحلال الملف. لا نخلط بين ضبط الزمن (Rvar) وضبط السعة (VGA/DAC).

### 11.2 ما الذي نحتفظ به من الدراسة

- R=100Ω وC=100pF وRvar=200–300kΩ نقطة بدء قابلة لإعادة البناء، لا قيم نهائية.
- كسب مرجعي 25×40=1000 هو كسب النموذج المنشور، وليس إلزاماً لجهازنا.
- الدراسة استخدمت مضخمات على ±15V؛ لذلك لا يجوز نقل مخططها إلى OPA2365 على 3.3V من دون إعادة تصميم كاملة.
- نحتاج مصدر bucking نظيفاً ومحدود الطاقة، وتوقيت SWb مضبوطاً نسبة إلى TX-off، وليس نبضة عشوائية من GPIO.
- يظل مسار الملف الخام مراقباً حتى لا تخفي عملية المعايرة هدفاً أو تغيراً أرضياً.

### 11.3 إعادة تقييم المضخمات

**OPA2365 لم يعد اختياراً أساسياً معتمداً.** مواصفاته على 3.3V مفيدة، لكن لا يوجد حتى الآن إثبات أنه يحقق headroom واستجابة gyrator وفرق الإشارة ضمن مخطط الدراسة بعد تحويله إلى تغذية مفردة. يبقى خياراً تجريبياً فقط إذا أثبتت محاكاة الدارة كاملة صلاحيته.

**OPA1612 أصبح مرشحاً أولياً أقوى للـAFE التناظري**:
- تغذية كلية 5–36V؛ يمكنه العمل على ±15V كما في الدراسة المرجعية، أو على سكة أخرى بعد محاكاة headroom. لا نثبت ±5V قبل معرفة swing المطلوب من VDCb/gyrator.
- GBW=40MHz، slew rate=27V/µs.
- ضجيج 1.1nV/√Hz.
- خرج rail-to-rail.
هذه المواصفات تجعله مرشحاً عملياً لدراسة gyrator ومسارات التضخيم التفاضلي، لكنه لا يصبح قطعة معتمدة قبل محاكاة الاستقرار والضجيج وsettling والـcommon-mode والـheadroom.

المصدر:
https://www.ti.com/product/OPA1612
https://www.ti.com/lit/ds/symlink/opa1612.pdf

### 11.4 إلغاء clamp BAV99 المباشر إلى 3.3V كحل معتمد

لا نعتمد ربط BAV99 من عقدة الملف عبر مقاومة مباشرة إلى 3.3V_AFE على أساس تيار clamp النظري وحده؛ لأن حقن التيار قد يرفع سكة التغذية ويعطل كل مراحل AFE أو يتجاوز تيار الحقن المسموح. تبقى BAV99 مجرد قطعة مرشحة في حماية مدروسة، وليس شبكة حماية معتمدة.

المطلوب في التصميم الجديد:
- حماية متعددة المراحل بعد حساب جهد الملف ومدة transient.
- مسار تفريغ/امتصاص طاقة مستقل لا يرفع مرجع 3.3V.
- مراقبة low-gain ذات مجال واسع.
- فصل/blanking للـhigh-gain path حتى recovery.
- إثبات absolute maximum وinjection current لكل IC قبل اعتماد قيم المقاومات والدايودات.

### 11.5 حالة القرار بعد التصحيح

- المبدأ الأساسي: time-domain bucking حقيقي بفرع SWb + VDCb + gyrator + VGA + differential amplifier.
- R/C/Rvar المنشورة نقطة بدء؛ لا شراء بناءً عليها وحدها.
- OPA1612 مرشح أولي للبحث والمحاكاة.
- OPA2365 وBAV99 لا يعتمدان في BOM حتى تثبت صلاحية شبكة التغذية والحماية.
- لا توجد بعد schematic قابلة للتصنيع أو BOM نهائية؛ يجب إتمام محاكاة transient للملف وفرع bucking وAFE كمنظومة واحدة.


## 12. مرشح تغذية ±15V متوافق مع بطارية 12V

ظهر جزء محدد يمكنه إعادة بناء تغذية الدراسة دون محولين منفصلين:

**TRACO POWER TEN 8-1223 — خيار بديل فقط**
- دخل 9–18V DC، مناسب لبطارية 12V.
- خرج مزدوج +15V / −15V.
- تيار حتى265mA لكل rail، قدرة8W.
- عزل1.5kV، وكفاءة نموذجية85%.
- Ripple/noise نموذجي50mVpp ضمن عرض قياس20MHz؛ يحتاج post-filter وdecoupling قبل AFE.
- الحجم DIP24، through-hole، مناسب للتركيب المصنع أو مقبس/لوحة فرعية، وليس قطعة SMD دقيقة.

مصادر:
- Datasheet: https://www.traco-powers.com/files/ca/ten-8-4822.pdf
- TME: https://www.tme.com/us/en-us/details/ten8-1223/dc-dc-converters/traco-power/ten-8-1223/
- DigiKey: https://www.digikey.com/en/products/detail/traco-power/TEN-8-1223/9383255

### التوفر المحلي
Power Lab يعرض **TEN8-4823** بسعر3800 دج، لكنه موديل دخل48V (36–75V)، وليس مناسباً لبطارية12V. لا نخلطه مع TEN8-1223.
لم يظهر مخزون جزائري مؤكد لـTEN8-1223 حتى هذا البحث. TME/DigiKey يعرضان مخزوناً دولياً، لكن الشحن والجمارك إلى الجزائر غير محسومين.

### القرار
بعد اختيار AD8336 كمرشح VGA، تراجع TEN8-1223 إلى بديل ±15V فقط إذا أُلغي AD8336. خط التغذية المفضل حالياً هو TEN8-1222 ±12V كما في القسم14. لا شراء لأي منهما قبل حساب الحمل والتموج والضجيج ومرشح post-filter.


## 13. اختيار VGA فعلي بدلاً من مرحلة كسب متغيرة مبهمة

ظهر مرشح مناسب جداً لوظيفة VGA في الدراسة:

**Analog Devices AD8336 — VGA DC-coupled**
- ضجيج دخل نموذجي3nV/√Hz.
- bandwidth صغير الإشارة115MHz، وlarge-signal 80MHz عند2Vpp.
- مدى كسب حتى60dB، والتحكم الخطي بالديسيبل 50dB/V.
- دخل/خرج single-ended وDC-coupled.
- تغذية مزدوجة ±3V إلى±12V.
- يحتوي preamplifier مستقل قابل لضبط كسبه 6–26dB.
- gain-control differential pins: (V_{GAIN}=V_{GPOS}-V_{GNEG})، وليس مقاومة رقمية عالية الجهد على feedback.
- استجابة تغيير كسب60dB نحو300ns.
- حزمة LFCSP؛ يجب تجميعها مصنعياً على PCB، لا لحام يدوي.

المراجع:
https://www.analog.com/en/products/ad8336.html
https://www.analog.com/media/en/technical-documentation/data-sheets/ad8336.pdf

### كيف نستخدمه؟
- مسار coil: OPA1612 كـpreamp ثابت الكسب (مرجع الدراسة25V/V).
- مسار bucking: gyrator OPA1612 ثم AD8336 لضبط سعة المرجع عبر VGA.
- بعد VGA: differential amplifier OPA1612 يطرح مرجع bucking من مسار الملف.
- DAC1_CH1/CH2 من STM32G474 يقدمان GPOS/GNEG عبر مقسمات مقاومة وRC attenuation مضبوطة؛ لا حاجة إلى buffer افتراضياً لأن gain pins واجهة تحكم عالية الممانعة، ويضاف buffer فقط إذا أثبت القياس الحاجة. كلا الخرجين يحددان ضمن0–0.6V.
- لا نربط DAC مباشرة قبل حساب مجال common-mode وabsolute maximum للـGAIN pins.

هذا يزيل الحاجة إلى MCP41HV51 في مسار VGA؛ يبقى MCP41HV51 فقط مرشحاً لضبط Rvar في gyrator.

## 14. اختيار تغذية تناظرية متوافقة مع AD8336

لأن AD8336 أقصى تغذية له ±12V، يصبح المرشح الأكثر اتساقاً:

**TRACO POWER TEN 8-1222**
- دخل9–18V، مناسب لبطارية12V.
- خرج +12V/−12V.
- 335mA لكل rail، 8W.
- كفاءة نموذجية87%، عزل1.5kV.
- Ripple/noise نموذجي50mVpp؛ يحتاج post-filter وdecoupling.

مصادر:
- TME: https://www.tme.com/ca/en/details/ten8-1222/dc-dc-converters/traco-power/ten-8-1222/
- DigiKey: https://www.digikey.com/en/products/detail/traco-power/TEN-8-1222/9383254
- TRACO TEN8 datasheet: https://www.traco-powers.com/files/ca/ten-8-4822.pdf

**القرار المؤقت:** ±12V هو خط AFE المرشح حالياً لأنه يسمح بتشغيل OPA1612 وAD8336 معاً دون خفض جهد إضافي. TEN8-1223 ±15V يتراجع إلى خيار بديل إذا أُلغي AD8336 أو أضيف تنظيم ±12V بعده.

### التوفر
لم يظهر TEN8-1222 أو AD8336 في مخزون جزائري مؤكد. TME/DigiKey يعرضان TEN8-1222 دولياً، وADI تعرض AD8336 كمنتج Production. لا شراء قبل حساب الحمل والتموج وتأكيد الشحن.

## 15. توزيع مضخمات AFE المقترح للمحاكاة

مرشح أولي:
- U1A OPA1612: gyrator.
- U1B OPA1612: coil preamp.
- U2A OPA1612: differential subtraction.
- U2B OPA1612: low-gain monitor/buffer أو post-filter stage بعد حساب الحاجة.
- U3 AD8336: bucking VGA.
- U4 TMUX6219: مفتاح SWb.
- U5 TMUX6219: high-gain blanking/enable بعد حماية المدخل.
- MCP41HV51: Rvar فقط إذا بقي الضبط الرقمي للمحث المكافئ مطلوباً.
- DAC1_CH1/CH2: تحكم AD8336 gain differential عبر resistor attenuators وRC.
- ADC1/ADC2: خرج الفرق + قناة مراقبة محمية.

هذا توزيع كتلي وليس schematic. يجب فحص استقرار gyrator، كسب Avr، مجال AD8336، common-mode، differential stage، وADC level-shift كمنظومة واحدة.


## 16. تدقيق واجهة تحكم AD8336 من الداتا شيت

تمت مراجعة Rev.G كاملة، وليس الاعتماد على عبارة 50dB/V فقط:

- عند التغذية المزدوجة، pin VCOM يوصل عادةً إلى GND التناظري.
- التحكم هو (V_{GAIN}=V_{GPOS}-V_{GNEG})، بميل نموذجي49.9dB/V.
- مجال gain-control العملي يقارب −0.6V إلى+0.6V؛ شكل Figure 11 يبين أن مجال common-mode المسموح عند ±12V واسع ويشمل 0–0.6V.
- لذلك يمكن استخدام DAC1_CH1 وDAC1_CH2 بعد buffer/attenuator لإنتاج GPOS وGNEG ضمن0–0.6V، بحيث يتغير الفرق من−0.6 إلى+0.6V. لا نخرج 3.3V مباشرة إلى أرجل GPOS/GNEG.
- VCOM=AGND عند dual supply.
- خرج AD8336 عند ±12V يحتاج حملاً لا يقل عن1kΩ لتحقيق مجال الخرج المحدد، ويجب ألا يتجاوز تيار الخرج الخطي20mA.
- عند ±12V، الحمل السعوي قد يتطلب مقاومة سلسلة20Ω للاستقرار وفق الداتا شيت.
- الداتا شيت تذكر offset output يصل إلى حدود مئات mV في حالات gain عالية؛ يجب معايرة offset وحفظه رقمياً، مع منع المعايرة من إزالة هدف حقيقي.
- لا نستخدم PWRA low-power mode في البداية؛ لأنه يخفض bandwidth إلى نحو35MHz، ونقيّم ذلك فقط إذا كان استهلاك الطاقة مهماً ولم يؤثر على شكل transient.

المصدر: AD8336 Rev.G، Table 3، Table 1، Figures 11 و15 و78، Sections VGA وDriving Capacitive Loads:
https://www.analog.com/media/en/technical-documentation/data-sheets/ad8336.pdf

## 17. شروط PCB لـAD8336

- LFCSP16 مع exposed pad غير متصل كهربائياً؛ يلحم إلى أرضي PCB لتحسين الاعتمادية والتبريد.
- يوصى بأربع طبقات مع أرضي/قدرة داخلية ومسارات قصيرة.
- فصل GPOS/GNEG وVCOM عن عقدة TX والـgate drive.
- إضافة نقاط اختبار GPOS/GNEG وVOUT وPRAO وVGAI و±12V.
- لا تضع AD8336 قرب MOSFET أو حلقة flyback؛ يثبت في منطقة AFE النظيفة.


## 18. توافق AD8336 مع OPA1612 على ±12V — هامش الدخل

تم تدقيق حدود common-mode لـOPA1612 من داتا شيت TI:
- مجال common-mode هو من (V_-+2V) إلى (V_+-2V).
- عند ±12V يصبح المجال الخطي تقريباً −10V إلى+10V.
- خرج AD8336 عند ±12V يمكن أن يصل تقريباً إلى ±9.75V مع حمل1kΩ أو أكبر.

لذلك **لا نوصل خرج AD8336 مباشرة إلى مدخل OPA1612 differential stage**؛ هامش common-mode سيكون ضيقاً جداً عند القمم. نضيف attenuator/matched input network قبل differential stage ليبقى دخل OPA1612 ضمن مجال أوسع (مرجع تصميم أولي ±8V أو أقل)، ثم نختار كسب differential stage لتعويض التوهين دون clipping.

يجب اختيار قيم شبكة التوهين والمقاومات المتطابقة بعد حساب:
- خرج AD8336 الأقصى عند كل gain.
- offset output عند gain العالي.
- الضجيج الحراري لشبكة المقاومات.
- CMRR الناتج عن mismatch.
- زمن settling والتحميل على AD8336.

المراجع:
- OPA1612 TI datasheet: https://www.ti.com/lit/ds/symlink/opa1612.pdf
- AD8336 Rev.G: https://www.analog.com/media/en/technical-documentation/data-sheets/ad8336.pdf

هذه إضافة headroom إلزامية؛ لا يُعتمد توصيل مباشر ولا schematic نهائي قبل محاكاتها.


## 19. إعادة توظيف OPA2365 في المكان الصحيح: ADC driver

OPA2365 لا يعود مضخم الاستقبال الأساسي ولا gyrator؛ لكنه يبقى مفيداً جداً كمرحلة نهائية بعد تكييف الإشارة:

- U5A: buffer/driver لقناة ADC1_IN1 / PA0.
- U5B: buffer/driver لقناة ADC2_IN2 / PA1.
- تغذية3.3V، rail-to-rail، GBW50MHz، slew25V/µs.
- قبل كل مدخل توجد شبكة مقاومات attenuator/level-shift تحوّل الإشارة التناظرية ذات المجال المزدوج إلى مجال آمن0–3.3V ومركز1.65V.
- مرجع1.65V يمكن أن يبدأ بمقسم منخفض الممانعة (مثلاً1kΩ/1kΩ) مع مكثف reservoir محلي؛ إذا أثبت اختبار ADC أن التموج/الممانعة يسببان خطأ، نضيف buffer مستقل.
- يضاف RC صغير عند مدخل ADC بعد buffer لتقليل charge kickback، وتحدد قيمته من زمن acquisition وsample capacitance في STM32G474.
- لا يتعرض OPA2365 ولا ADC مباشرة إلى خرج AD8336 أو ملف البحث أو عقدة flyback.

بهذا نستخدم OPA2365 في بيئة تغذيته الطبيعية 3.3V كـADC interface، ونترك ±12V analog front-end لمكونات OPA1612/AD8336.


## 20. شبكة تحكم AD8336 الأولية بالأرقام

نقطة بدء عملية لتوليد GPOS/GNEG من DAC1_CH1/CH2:
- Rtop=10kΩ من خرج DAC إلى عقدة التحكم.
- Rbottom=2.2kΩ من العقدة إلى AGND.
- Rseries=1kΩ من العقدة إلى رجل GPOS أو GNEG.
- Cfilter=10nF من رجل التحكم إلى AGND.
- VCOM=AGND.

النسبة DC التقريبية:
[
k=\frac{2.2}{10+2.2}=0.1803
]
وعند DAC=3.3V:
[
V_{GPOS/GNEG,max}\approx0.595V
]
إذن:
[
V_{GAIN}=V_{GPOS}-V_{GNEG}\approx-0.595..+0.595V
]
وبميل49.9dB/V يكون مجال التغيير النظري قرابة59.4dB، قريباً من مدى AD8336 المنشور60dB.

دقة DAC12-bit بعد المقسم:
- خطوة الجهد عند gain pin≈0.145mV.
- خطوة الكسب≈0.0072dB لكل LSB تقريباً.

هذه القيم **شبكة أولية للمحاكاة** وليست BOM نهائية. نتحقق من الحمل الفعلي للـgain pins، استقرار DAC، زمن RC، noise، ومجال common-mode قبل PCB.

### معايرة الكسب
Firmware ينفذ sweep بطيئاً لرمزي DAC، ويقيس VOUT عبر مسار ADC monitor، ثم يخزن slope/intercept لكل لوحة:
[
G_{dB}=G_0+S\cdot V_{GAIN}
]
حيث يبدأ S≈49.9dB/V وG0≈16.4dB عند preamp4×، ثم تُستبدل القيم المقاسة بالقيم الفعلية. لا تتم المعايرة أثناء وجود هدف محتمل.


## 21. مفتاحا SWb وHigh-gain: اختيار TMUX6219

بعد مقارنة المفاتيح ذات مجال ±12V، أصبح **TI TMUX6219** مرشحاً أفضل من TMUX1134:
- SPDT أحادي القناة.
- يعمل بتغذية مزدوجة ±4.5V إلى±18V؛ مناسب لـ±12V_AFE.
- RON نموذجي2.1Ω.
- تيار مستمر حتى330mA (حزمة VSSOP)، أعلى من تيار bucking المرجعي المتوقع.
- Charge injection نحو−10pC.
- bandwidth43MHz.
- منطق تحكم1.8V متوافق مع GPIO/HRTIM 3.3V.
- Break-before-make وfail-safe logic.

المصادر:
https://www.ti.com/product/TMUX6219
https://www.ti.com/lit/ds/symlink/tmux6219.pdf

### التوزيع المقترح
- U4 TMUX6219: مفتاح SWb لفرع VDCb/gyrator.
- U5 TMUX6219: فصل/وصل مسار high-gain AFE بعد حماية low-gain.
- كلاهما على ±12V_AFE؛ EN من HRTIM، وSEL ثابت أو يختار مساراً آمناً.
- TMUX1134 (5.5V max) لم يعد الاختيار الأساسي؛ لا يصلح لتمرير الإشارة ثنائية القطبية على ±12V.

## 22. قيمة VDCb وخط bucking الأولي للمحاكاة

قيمة VDCb لم تذكرها الورقة؛ نحتاج فرضية واحدة لبدء المحاكاة، لا فتح بدائل كثيرة:

**Baseline simulation:**
- VDCb = 9V regulated.
- R = 100Ω.
- C = 100pF C0G.
- Rvar = 255kΩ.
- Lvar النظري = 2.55mH.
- τ النظري = 25.5µs.
- مع RON≈2.1Ω لمفتاح TMUX6219 يصبح Rseries≈102.1Ω، وτ الفعلي الأولي≈25.0µs.
- تيار bucking الابتدائي التقريبي = 9V/102.1Ω ≈88mA.
- الطاقة الابتدائية المخزنة تقريباً (0.5×2.55mH×(88mA)^2≈9.9µJ).

VDCb=9V يترك headroom تحت ±12V للـTMUX6219، ويولد طاقة كافية كبداية مع إمكانية ضبط السعة عبر AD8336. لا يُعتمد كقيمة نهائية حتى نحاكي شكل spike ونسبة المطابقة مع coil response.

مصدر 9V يشتق من +12V_AFE عبر regulator منخفض الضجيج؛ رقم المنظم لم يحدد بعد. لا نأخذ VDCb مباشرة من بطارية غير منظمة حتى لا يتغير bucking مع هبوط البطارية.

## 23. توقيت مفاتيح bucking وblanking

- PA9 / HRTIM1_CHA2 يطلق EN لمفتاح SWb.
- PA10 / HRTIM1_CHB1 يطلق EN لمفتاح high-gain blanking.
- PA8 / HRTIM1_CHA1 يطلق TX gate driver.
- COMP2 recovery event يعيد تمكين high-gain عبر HRTIM بعد minimum dead-time.
- TMUX6219 SEL يثبت على المسار المختار؛ لا نبدل SEL أثناء transient.

المراجع:
- STM32G474 datasheet Table 12: PA10 supports HRTIM1_CHB1.
- UM2505 Rev.7: PA10 على CN9 pin3 / Arduino D2.


## 24. تصحيح نهائي لنوع digital potentiometer في gyrator

تم إسقاط MCP41100 نهائياً من هذا الموضع؛ حد أطرافه التناظرية5.5V لا يكفي مع gyrator على ±12V.

**القطعة الصحيحة المرشحة: Microchip MCP41HV51-104E/ST**
- 100kΩ، 8-bit، 256 taps، SPI، حزمة TSSOP-14.
- مجال أطراف تناظرية حتى±18V (أو36V أحادي)، مناسب لـ±12V.
- منطق رقمي2.7–5.5V؛ يعمل مع STM32 3.3V.
- Wiper resistance نموذجي75Ω.
- تيار طرفي أقصى للنسخة100kΩ نحو6.5mA؛ تيار gyrator المتوقع أقل بكثير.
- يستخدم مع مقاومة ثابتة200kΩ للحصول على مجال Rvar≈200–300kΩ.
- خطوة المقاومة≈392Ω، وخطوة τ≈0.039µs عند C=100pF، وهي أدق من حاجة الضبط الأولي.
- POR wiper code=0x7F (midscale) يعطي نحو49.8kΩ؛ مع200kΩ ثابتة يصبح Rvar≈249.8kΩ وτ≈25µs، أي نقطة بدء مناسبة تلقائياً. Firmware يعيد ضبط الكود بعد startup إذا احتاج معايرة أدق.
- يلزم احترام power sequencing: rails التناظرية V+/V− قبل تطبيق الجهد على أطراف A/B/W، مع إبقاء SHDN/CS في حالة آمنة حتى استقرار ±12V وVL.

المصادر:
https://www.microchip.com/en-us/product/MCP41HV51
https://ww1.microchip.com/downloads/aemDocuments/documents/MSLD/ProductDocuments/DataSheets/MCP41HVX1-Data-Sheet-20005207.pdf

هذه القطعة الآن مرشح Rvar الصحيح؛ لا شراء قبل التأكد من توصيلات A/W/B في gyrator ومحاكاة حدود terminal voltage والتيار.


### توصيل أطراف MCP41HV51-104E/ST

- V+ = +12V_AFE.
- V− = −12V_AFE.
- DGND = AGND (0V).
- VL = +3.3V digital.
- P0A/P0W/P0B: شبكة Rvar؛ يستخدم P0W مع P0B كرهيستات، ويترك الطرف الآخر وفق مخطط gyrator.
- SCK=PB13، SDI=PB15، CS=PB6.
- SDO غير موصول حالياً (لا نحتاج readback).
- WLAT يربط DGND لأن تحديثات wiper غير متزامنة مع zero crossing.
- SHDN يربط VL عبر10kΩ ليبقى غير فعال؛ لا يحتاج GPIO.
- POR code=0x7F؛ يعطي نحو49.8kΩ من pot، فينتج Rvar≈249.8kΩ مع200kΩ ثابتة.

يجب تثبيت اختيار P0W/P0B في schematic النهائي بعد مراجعة Fig.3 gyrator، مع تجنب وضع الجهد على أطراف pot خارج V+ وV−.
