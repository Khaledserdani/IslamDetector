# إسلام 2 — هندسة إرسال TX ومسار تفريغ طاقة الملف والحماية
التاريخ: 2026-11-17
الفرع: hardware/islam-nextgen-final-platform
الحالة: مراجعة طوبولوجيا وحسابات؛ لا مخطط نهائي ولا قيم مكونات معتمدة.

## 1) القرار الأساسي
يجب تصميم TX كمرحلة طاقة مستقلة عن RX وMCU. لا يُسمح أن يكون ESP32 أو STM32 أو بوابة MOSFET أو مدخل ADC جزءاً من مسار تيار الملف العالي. المتحكم يرسل أمر توقيت معزولاً/محمياً، ومرحلة الطاقة تنفذ النبضة وتعيد قياس التيار والجهد.

## 2) طوبولوجيا الاختبار المرجعية
الطوبولوجيا الأولية المراد تقييمها:
- مصدر TX محدود التيار مع مكثف bulk محلي قريب من مرحلة القدرة.
- ملف TX موصول إلى خط التغذية.
- N-channel MOSFET low-side switch مع gate driver قريب من MOSFET.
- current sense في مسار رجوع TX، مع Kelvin routing.
- شبكة clamp/energy recovery مصممة لإيقاف تيار الملف بسرعة مع إبقاء VDS ضمن هامش آمن.
- مسار RX منفصل مادياً وكهربائياً، مع حماية/تعويض bucking قبل الكسب العالي.

هذه طوبولوجيا مرجعية للمقارنة وليست مخططاً نهائياً؛ قد تتغير إذا أظهرت قياسات الملف أو شكل الموجة أن بنية أخرى أفضل.

## 3) لماذا لا نضع دايود freewheel عادي وننتهي؟
الدايود منخفض الجهد يتيح تياراً دائراً بعد فصل MOSFET، لكنه يخفض الجهد العكسي على الملف ويطيل زمن هبوط التيار. هذا قد يضعف/يؤخر بداية نافذة قياس PI ويغير شكل الإثارة.
في المقابل، clamp بجهد أعلى يسرّع هبوط التيار، لكنه يرفع جهد MOSFET والضغط على شبكة الحماية. المطلوب موازنة زمن انطفاء التيار مع تحمل الجهد والطاقة والحرارة.

## 4) الحسابات التي يجب أن تدخل ملف التصميم
### الطاقة المخزنة قبل فصل TX
E_L = 0.5 × L × I_peak²

حيث L محاثة الملف عند ظروف التشغيل الفعلية، وI_peak تيار الملف عند لحظة الفصل.

### هبوط التيار التقريبي
إذا كان U هو الجهد العكسي الفعال على الملف أثناء التفريغ، وبإهمال مقاومة الملف والتغيرات غير الخطية:
t_decay ≈ L × I_peak / U

في طوبولوجيا low-side clamp على MOSFET، لا نساوي تلقائياً بين U وجهد clamp على MOSFET؛ يجب احتساب جهد التغذية واتجاهات الجهد في الحلقة. في تقريب شائع يكون جهد الملف العكسي مرتبطاً بـ VDS_clamp − V_supply، مع اعتماد الإشارة والحدود على الرسم الفعلي.

### متوسط قدرة التفريغ
P_clamp,avg ≈ E_dissipated_per_pulse × f_rep

هذا تقدير أولي فقط. الحساب الدقيق يدمج v(t)×i(t) في عنصر clamp، ويحسب أيضاً الطاقة المفقودة في مقاومة الملف والأسلاك والعناصر الأخرى، وأي طاقة تعود إلى مكثف التغذية.

## 5) قواعد اختيار MOSFET وGate Driver
لا نختار MOSFET من VDS وID الاسميين فقط. يجب التحقق من:
- VDS(max) مع أعلى جهد clamp وتغذية TX والـovershoot الناتج من parasitic inductance.
- SOA أثناء أي حالة linear/active clamp؛ لا نفترض أن MOSFET يتحمل البقاء في المنطقة الخطية لمجرد أنه يتحمل التيار في حالة ON.
- RDS(on) عند VGS وحرارة التشغيل الحقيقية.
- total gate charge Qg وMiller charge، لا Ciss وحدها.
- قدرة gate driver على source/sink peak current المطلوب وزمن الشحن/التفريغ، وحدود VGS.
- inductance مسار gate وsource، مقاومة gate، وKelvin source عند الحاجة.
- switching loss وحرارة التكرار، وليس conduction loss فقط.
- avalanche rating ليست تصريحاً باستخدام avalanche متكرر كطريقة تشغيل طبيعية.

يُستخدم gate driver مناسب لمستوى MOSFET المختار، وتوضع مقاومة gate وgate-source pulldown وفق حساب الاستقرار وسرعة الحافة والـEMI. لا نثبت TC4420 أو أي driver قبل اختيار MOSFET وقياس Qg وتحديد جهد القيادة.

## 6) قواعد اختيار clamp
يجب اختيار واحد من المسارات التالية بعد المحاكاة والقياس:
A. TVS/clamp عبر MOSFET أو مسار التفريغ.
B. TVS + diode عبر الملف/الحمل وفق قطبية التوصيل.
C. active clamp أو استرداد طاقة إلى مكثف/rail إذا بررت الكفاءة والتعقيد ذلك.

لكل خيار يجب حساب:
- أقصى clamp voltage عند تيار النبضة ودرجة الحرارة، وليس رقم standoff وحده.
- طاقة النبضة الواحدة وتكرارها والقدرة المتوسطة.
- جهد MOSFET الفعلي VDS بما يشمل parasitic overshoot.
- زمن هبوط تيار الملف.
- حرارة TVS/المقاومة/المفتاح وشروط التبريد.
- أثر clamp على شكل TX وعلى transient المقاس في RX.

لا يُسمح باعتماد TVS اعتماداً على رقم مثل SMBJ58A وحده؛ يلزم اختيار منحنى clamp الفعلي عند تيارنا، وتحمّل النبضات، والطاقة والتكرار، وحدود MOSFET.

## 7) الحماية والتحكم الآمن
- حد تيار hardware مستقل عن البرنامج.
- fuse مناسب لخصائص التيار والنبضات، مع عدم اعتباره بديلاً عن current limit سريع.
- undervoltage/overvoltage monitoring لمصدر TX.
- interlock يمنع TX إذا لم تكن حالة gate driver أو التغذية صحيحة.
- default gate-off عند reset أو boot أو فقد الاتصال.
- watchdog مستقل يوقف TX عند تعطل البرنامج.
- إيقاف طوارئ يقطع قيادة gate، لا يكتفي بإرسال أمر برمجي.
- قياس تيار TX وVDS/جهد الملف في نقاط اختبار آمنة.
- حماية من عكس القطبية وقصر الملف وفتح الملف.
- منع رجوع طاقة التفريغ إلى Power Bank أو خط 5V الخاص بالمنطق إلا إذا صُمم مسار استرداد الطاقة لهذا الغرض.

## 8) فصل TX عن RX واللوحة الرقمية
- حلقة تيار TX قصيرة وعريضة ومنخفضة الحث.
- لا تمرر تيار TX في أرضي المضخم أو مرجع ADC.
- افصل return power عن analog return، واربطهما عند نقطة مدروسة واحدة/شبكة مرجعية حسب layout.
- لا تضع ملف bucking أو مدخل المضخم قرب MOSFET أو gate loop.
- ضع مقاومات/مكثفات gate وdecoupling قرب أطرافها.
- استخدم قياس Kelvin للـshunt.
- راقب ground bounce بين أرضي AFE وأرضي MCU أثناء TX.
- لا تستخدم سلك USB أو shield كمسار رجوع تيار نبضة.

## 9) تسلسل اختبار آمن
1. افحص الدارة دون ملف وبجهد منخفض ومصدر محدود التيار.
2. اختبر gate waveform وVGS على حمل وهمي.
3. استخدم ملفاً/محاثة اختبار معلومة وبطاقة منخفضة، وقس VDS وI_L وVGS في آن واحد.
4. تحقق من clamp voltage وdecay time وحرارة MOSFET/TVS.
5. زد الطاقة تدريجياً فقط بعد مطابقة الحسابات مع القياس.
6. بعد ثبات TX، أضف RX أولاً على طاقة منخفضة مع حماية وقياس differential.
7. اختبر clipping/recovery قبل أي اختبار أهداف.

لا تجرى هذه الاختبارات على مصدر غير محدود التيار أو دون معدات قياس مناسبة ومسبار جهد مصنف.

## 10) ما يلزم قبل اختيار القطع
لا يمكن حساب قيم MOSFET وTVS وshunt وgate resistor وfuse قبل قياس/تحديد:
- L وR للملف الحقيقي، وتغيرهما مع التردد/الحرارة.
- I_peak المطلوب أو الحد الأعلى المسموح.
- V_supply ونطاق البطارية.
- pulse width وrepetition frequency وduty cycle.
- أقصى زمن فصل مسموح لبدء نافذة RX.
- جهد MOSFET المسموح وهامش overshoot.
- طريقة clamp وتوزيع الطاقة بين العناصر.

أي قائمة قطع قبل هذه المعطيات ستكون تخميناً لا تصميمًا موثوقاً.

## 11) المراجع
- TI, Switching inductive loads — clamp-voltage versus current-decay tradeoff:
https://www.ti.com/document-viewer/lit/html/SLVAF04
- Infineon, Power MOSFET avalanche design guidelines (2023):
https://www.infineon.com/assets/row/public/documents/24/42/infineon-power-mosfet-avalanche-design-guidelines-applicationnotes-en.pdf
- Infineon, Designing with power MOSFETs — single vs repetitive avalanche:
https://www.infineon.com/assets/row/public/documents/24/42/infineon-designing-with-power-mosfets-applicationnotes-en.pdf
- Nexperia IAN50020 — MOSFETs in power switch applications:
https://www.nexperia.com/applications/interactive-app-notes/IAN50020_Power_Switch_MOSFETs

## 12) ما لم يثبت بعد
- لم تُقَس محاثة/مقاومة ملف إسلام الفعلي.
- لم يحدد تيار TX أو pulse width أو repetition rate نهائياً.
- لم يتم اختيار MOSFET أو driver أو clamp أو fuse.
- لم يُبنَ أو يختبر TX prototype.
- لا توجد قيم شراء معتمدة.
