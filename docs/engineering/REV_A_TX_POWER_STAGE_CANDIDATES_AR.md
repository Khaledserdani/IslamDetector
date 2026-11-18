# مرشحو مرحلة TX للـRev A — مراجعة MOSFET وسائق البوابة

**الحالة:** مقارنة مرشحين وليست BOM معتمدة أو مخططاً صالحاً للتوصيل.  
**التاريخ:** 2026-11-18  
**الفرع:** `hardware/rev-a-measurement-design`

## 1. الطوبولوجيا المفترضة للمقارنة

مصدر TX منخفض الجهد → ملف Mono Spiral → Drain لـN-MOSFET low-side → Source إلى مسار الرجوع. شبكة clamp مستقلة تعاكس تيار الملف بعد إطفاء MOSFET. هذا المسار يظل افتراضاً حتى إغلاق تصميم clamp والقياس.

## 2. مرشح MOSFET: IRFP260NPbF

البيانات المنشورة من Infineon (Rev 2.1، 2024-10-08):

| الخاصية | القيمة المنشورة | ملاحظة التصميم |
|---|---:|---|
| VDS | 200V | مرشح مبدئي لهامش جهد؛ لا يعتمد قبل قياس overshoot |
| RDS(on) max | 40mΩ عند VGS=10V | لا تنطبق القيمة عند VGS=3.3V |
| ID continuous | 50A عند TC=25°C وVGS=10V | الرقم ليس هدف تشغيلنا ولا يعوض SOA |
| Qg max | 234nC عند VGS=10V، ID=28A، VDS=160V | شحنة مرتفعة نسبياً؛ driver يجب أن يشحنها ويفرغها بسرعة مضبوطة |
| Qgd max | 110nC | يجب الانتباه إلى Miller وdv/dt |
| VGS absolute max | ±20V | يلزم منع أي overshoot على البوابة |
| Package | TO-247AC | كبير نسبياً ويحتاج تثبيتاً حرارياً/ميكانيكياً |
| EAS single pulse | 560mJ | لا يستخدم لتبرير avalanche متكرر |
| EAR repetitive | 30mJ | مشروط بملاحظات الداتا شيت؛ ليس بديلاً عن clamp |

### التقييم
- **نقطة قوة:** VDS=200V وRDS(on)=40mΩ عند10V، ما يجعله مرشحاً أولياً مع clamp منخفض/متوسط الجهد.
- **نقطة ضعف:** Qg يصل234nC والحزمة TO-247 أكبر مما نحتاجه مبدئياً. يجب مقارنة بديل أحدث بجهد150–200V وشحنة بوابة أقل، بشرط SOA حقيقي وRDS(on) مضمون عند جهد القيادة.
- **قرار:** IRFP260NPbF يبقى مرشح A للمقارنة، لا اختياراً نهائياً. لا نثبت القطعة حتى نعرف VDS الحقيقي مع overshoot ومدة/تكرار النبض.

## 3. مرشح Gate Driver: TC4420

بيانات Microchip الرسمية:
- تغذية VDD من4.5V إلى18V.
- دخل HIGH مضمون من2.4V، لذا إشارة منطق3.3V متوافقة من حيث VIH.
- خرج non-inverting، تيار peak يصل6A، وتأخير نموذجي55ns، وممانعة خرج نموذجية تقارب2.5Ω.
- خرج البوابة يتبع VDD؛ لذلك تغذية driver بجهد10–12V تعطي VGS أعلى من قيادة3.3V، لكن يجب ضبط VGS ضمن ±20V.
- TC4420 لا يحتوي قفل overcurrent/thermal مستقل؛ الحماية والـone-shot والـfault latch خارجية وإلزامية.

### حساب gate-charge تقريبي
باستخدام Qg(max)=234nC وVdrive=10V:
- طاقة قيادة البوابة التقريبية لكل انتقال شحن: Qg×Vdrive≈2.34µJ.
- عند100Hz، متوسط قدرة الشحن التقريبي≈0.234mW؛ وعند1kHz≈2.34mW.
- إذا افترضنا Rg=10Ω وRout≈2.5Ω، فالتيار الأولي التقريبي عند10V≈0.8A، وزمن Qg/I التقريبي≈0.29µs. هذه أرقام screening؛ شكل تيار Miller والـgate plateau والتوصيلات يحدد الزمن الحقيقي.

### التقييم
TC4420 مناسب مبدئياً لقيادة MOSFET ذي Qg مرتفع مع حافة سريعة، لكن لا يعني أن 6A مطلوب أو أن مقاومة10Ω ثبتت. يجب ضبط Rg وturn-off path بعد اختيار MOSFET ومراجعة EMI والـVGS ringing. لأن TC4420 لا يملك Enable pin مخصصاً، يجب تمرير دخله عبر hardware one-shot/logic gate/fault latch بحيث يكون LOW افتراضياً ويُقطع عند أي fault.

## 4. توافق الزوج المرشح

| البند | النتيجة الأولية |
|---|---|
| RP2040 3.3V logic → TC4420 input | متوافق من ناحية VIH=2.4V، بشرط مستوى LOW/boot/reset مضمون |
| TC4420 VDD=10V → IRFP260N gate | مناسب مبدئياً لتحقيق شرط RDS(on) المنشور عند VGS=10V |
| Qg 234nC مع TC4420 6A peak | قدرة قيادة كافية مبدئياً؛ نضبط edge عبر Rg |
| VDS 200V مع سيناريو clamp | 42/72/112V ideal في حالات clamp30/60/100V على مصدر12V، لكن لا نثبت الهامش قبل قياس overshoot |
| حماية التيار/النبضة | غير موجودة داخل هذا الزوج؛ يجب توفير interlock مستقل |
| الحماية من transient | لا يوفرها MOSFET/driver وحدهما؛ clamp محسوب وlayout منخفض الحث ضروريان |

## 5. ما لا نثبته بعد

1. رقم MOSFET نهائي أو footprint نهائي.
2. رقم Gate Driver نهائي أو جهد تغذيته النهائي.
3. قيمة Rg أو Rgs أو gate zener.
4. موضع وقيمة TVS/RCD/snubber أو diode.
5. قيمة الشنت/عتبة comparator.
6. حد VDS المسموح الفعلي بعد overshoot.
7. صلاحية IRFP260N للحرارة والـSOA مع النبضات المتكررة في PCB النهائي.

## 6. بوابات اعتماد القطع

- الحصول على waveform/محاكاة transient للطوبولوجيا المحددة.
- حساب VDS peak مع tolerances وparasitics ثم هامش derating.
- مراجعة SOA عند VDS/ID/20µs ودرجة حرارة بداية واقعية، وZth مع تكرار100Hz ثم المعدل المستهدف.
- حساب conduction + switching + gate-drive losses.
- مراجعة Qg/Qgd عند ظروف أقرب للتشغيل، وضبط Rg وVGS clamp.
- إثبات أن comparator/one-shot يقطعان النبضة قبل تجاوز حدود الجهاز.
- اختبار حمل بديل محدود التيار قبل توصيل ملف البحث.

## 7. المصادر الرسمية

- Infineon IRFP260NPbF datasheet Rev.2.1: https://www.infineon.com/assets/row/public/documents/24/49/infineon-irfp260n-datasheet-en.pdf
- Microchip TC4420 datasheet DS21419: https://ww1.microchip.com/downloads/en/DeviceDoc/21419D.pdf
- Microchip TC4420 product page: https://www.microchip.com/en-us/product/tc4420
- Microchip AN798 (TC4420/4429): https://www.microchip.com/en-us/application-notes/an798
- Nexperia SOA/avalanche application notes: https://assets.nexperia.com/documents/application-note/AN10273.pdf and https://assets.nexperia.com/documents/application-note/AN11158.pdf


## 8. أثر تأخير comparator على اختيار حد التيار

المواصفة الوظيفية لقفل TX في `REV_A_TX_INTERLOCK_SPEC_AR.md` توسعت لتشمل تأخير comparator + latch + driver. نموذج `current_limit_response()` يبين أن عتبة3A في سيناريو12V/L50µH/R0.9Ω تصل بعد14.16µs، ثم يزيد التيار إلى3.184A إذا كان التأخير الكلي1µs، أو3.889A إذا كان5µs. لذلك لا يكفي أن تكون عتبة comparator أقل من حد MOSFET؛ يجب حساب التيار الفعلي عند إطفاء البوابة وVDS/الطاقة أثناءه. لا يوجد comparator أو shunt محدد بعد.


## 9. بديل MOSFET منخفض Gate Charge — TI CSD19531KCS

تمت إضافة مرشح منافس أقوى من ناحية شحنة البوابة، بعد مراجعة داتا شيت TI SLPS407D Rev.D (May 2024):

| الخاصية | IRFP260NPbF | CSD19531KCS |
|---|---:|---:|
| VDS | 200V | 100V |
| RDS(on) max عند10V | 40mΩ | 7.7mΩ |
| Qg max | 234nC | 49nC |
| Qgd typ | 110nC | 7.5nC |
| الحزمة | TO-247AC | TO-220 |
| RθJC max | 0.50°C/W | 0.7°C/W |

**لماذا يستحق CSD19531KCS التقدم؟**
- شحنة البوابة القصوى أقل بنحو4.8 مرات، وMiller charge أقل بنحو14.7 مرة؛ هذا يقلل العبء على TC4420 ويساعد على قطع أنظف وأسرع.
- RDS(on) max عند10V أقل بكثير، والحزمة TO-220 أصغر.
- 100V يعطي هامشاً نظرياً يقارب2.86 مرة فوق VDS المثالي ~35V المحسوب من clamp، لكن هذا الهامش لا يُعتمد قبل قياس overshoot. إذا اقتربت القمة من80V أو تجاوزتها، لا نعتمد 100V مع derating أولي80%.

**القرار الحالي:** CSD19531KCS أصبح مرشح A للمقارنة من حيث Qg/حجم الحزمة، وIRFP260NPbF يبقى مرشح B احتياطياً لهامش جهد أعلى. لا يعتمد أيهما قبل:
1. إثبات أقصى VDS بما فيه overshoot مع clamp الحقيقي.
2. فحص SOA عند التيار والجهد ومدة النبضة الفعلية، مع تكرار100Hz ودرجة حرارة البداية.
3. مراجعة gate drive وVGS ringing والـlayout.
4. التأكد من حالة التوفر والأصالة والمصدر المحلي/الشحن.

لا تفسر 100V على أنه موافقة تشغيل؛ لا توصيل TX قبل اكتمال الحماية والقياس.


## 10. قرار قيادة البوابة ومقارنة MOSFET المحدثة — 2026-11-18

### 10.1 تصحيح مصدر البيانات
- TI CSD19531KCS: Qg max49nC، Qgd typ7.5nC، RDS(on) max7.7mΩ عندVGS=10V، VDS100V، TO-220، RθJC max0.7°C/W، وEAS single-pulse 180mJ عندID60A/L0.1mH/RG25Ω (شروط الاختبار مهمة ولا تُنقل كضمان لنبضتنا).
- Infineon IRFP260NPbF: Qg max234nC، Qgd max110nC، RDS(on) max40mΩ عند10V، VDS200V، TO-247، RθJC max0.5°C/W.
- CSD يخفض Qg بنحو4.78× وQgd بنحو14.67×، ويقلل خسارة التوصيل النظرية عند التيار نفسه؛ لكنه يملك نصف تصنيف الجهد.

### 10.2 مراجعة TC4420 مع مرشح CSD
Microchip TC4420:
- تغذية4.5–18V؛ دخل CMOS/TTL، VIH الأدنى2.4V، لذا منطق3.3V متوافق مبدئياً.
- تيار خرج قِمّي6A؛ مقاومة خرج منخفضة تقارب2.5Ω؛ تأخير انتشار55ns typ/75ns max عند25°C؛ rise/fall25ns typ/35ns max عند2500pF. عبر نطاق الحرارة الأوسع قد يصل تأخير الانتشار إلى100ns max وrise/fall إلى60ns max.
- TC4420 لا يملك Enable مستقل. يجب أن يفرض fault latch/one-shot إشارة IN إلى LOW، مع pull-down، وأن يكون الإطفاء العتادي غير متزامن.
- لا نستنتج زمن إطفاء MOSFET من 55ns وحدها؛ يجب إدخال Qgd وRg ومقاومة الخرج وcommon-source inductance وMiller plateau وقياس VGS/VDS.

### 10.3 خطة اختيار Rg — لا تثبيت قيمة قبل القياس
- قيم البداية على منصة اختبار MOSFET وحمل بديل: Rg=4.7Ω، 10Ω، 15Ω؛ هذه نقاط اختبار وليست BOM.
- لكل قيمة: قِس VGS عند أرجل MOSFET وVDS وdrain current، turn-off delay/fall، ringing/false turn-on، والـovershoot.
- لا تعتمد أسرع حافة تلقائياً؛ اختر أصغر overshoot مع إطفاء سريع وبدون ringing أو إعادة تشغيل Miller.
- Gate pulldown مستقل، ومسار Gate/Source Kelvin قصير، وdriver decoupling ملاصق.

### 10.4 SOA وقرار المرشح
- تيار نهاية النبضة النظري حتى2.55A، وزمن demagnetization قرابة9µs، لكن هذا لا يمثل تلقائياً مدة linear stress على MOSFET؛ مرحلة انتقال البوابة والـparasitics هي التي يجب قياسها.
- TI يحدد SOA single-pulse وZθJC curves؛ لا يجوز استخدام EAS كبديل عن SOA، ولا افتراض أن تصنيف 285A pulsed current يعني صلاحية أي نقطة VDS/ID.
- ترتيب الدراسة: CSD19531KCS مرشح A، IRFP260NPbF مرشح B. **لا اعتماد شراء** حتى قياس VDS peak على الحمل البديل، إثبات margin مع derating متفق عليه، والتحقق من SOA وحرارة الوصلة.
- إذا تجاوز VDS peak ميزانية 80V المقترحة مبدئياً لمرشح100V، نوقف اعتماد CSD ونراجع clamp/layout أو ننتقل لفئة جهد أعلى. 80V حد مراجعة محافظ أولي وليس مواصفة تشغيل.

### 10.5 المصادر
- TI CSD19531KCS SLPS407D Rev.D: https://www.ti.com/lit/ds/symlink/csd19531kcs.pdf
- Infineon IRFP260N Rev.2.1: https://www.infineon.com/assets/row/public/documents/24/49/infineon-irfp260n-datasheet-en.pdf
- Microchip TC4420 DS21419D: https://ww1.microchip.com/downloads/en/DeviceDoc/21419D.pdf
