# مرشح مراقبة تيار TX السريعة — TLV3201 + Shunt

**الحالة:** مرشح أولي للتحليل، لا BOM معتمد أو توصيل نهائي.  
**التاريخ:** 2026-11-18  
**الفرع:** `hardware/rev-a-measurement-design`

## 1. لماذا نحتاج comparator مستقلاً؟

حد التيار البرمجي لا يحمي MOSFET أو الملف إذا تأخر firmware أو توقف. يجب أن يقطع comparator العتادي مسار Gate Enable عبر fault latch، بينما one-shot مستقل يفرض أقصى عرض نبضة حتى لو تعطل comparator أو ظل طلب MCU عالقاً.

## 2. مرشح comparator: TI TLV3201

من الداتا شيت SBOS561C، Rev C (May 2024):
- Propagation delay: 40ns typical، و100ns max عبر نطاق الحرارة (75ns max عند25°C) عبر مدى الحرارة في شروط القياس المحددة.
- Input offset: 1mV typical، 3mV max عند25°C، و4mV max من−40 إلى125°C.
- Common-mode input extends 200mV beyond either rail.
- Supply 2.7–5.5V، push-pull output، و40µA typical quiescent current.
- الحزمة: SOT-23-5 أو SC70-5.

**التقييم:** 55ns max مناسب مبدئياً لنبضة20µs؛ دقة offset أفضل من TLV3501 رغم أن TLV3501 أسرع (4.5ns) لكن offset max≈6.5mV واستهلاكه≈3.2mA. لا نحتاج 4.5ns إذا كانت ميزانية قطع كاملة أقل من1µs؛ دقة العتبة والضوضاء أهم. يجب التحقق من overdrive الحقيقي، common-mode أثناء الضوضاء، وسلوك output مع latch.

## 3. مثال شنت منخفض الجانب — ليس اختياراً نهائياً

نختبر حسابياً 50mΩ low-side Kelvin shunt مع عتبة3A:
- جهد الشنت عند3A: 150mV.
- قدرة الشنت اللحظية عند3A: 0.45W.
- طاقة تقريبية خلال20µs عند تيار ثابت3A: 9µJ؛ هذه قيمة حدية عليا لأن التيار يرتفع تدريجياً.
- عند duty cycle=20µs×100Hz=0.2%، متوسط القدرة التقريبي على 50mΩ عند3A مستمر طوال النبضة≈0.9mW.
- مع افتراض offset comparator ±4mV، وشنت±1%، ومرجع عتبة مثالي150mV، يصبح حد trip النظري تقريباً2.89–3.11A قبل أخطاء مرجع العتبة والضوضاء والـKelvin routing.

هذا مثال يوضح المفاضلة بين حساسية offset وهبوط الجهد؛ لا يعني اعتماد 50mΩ أو3A. يجب اختيار resistor low-inductance pulse-rated، وقياس الضوضاء والـsource bounce، ومراجعة مقاومة الشنت الفعلية مع الحرارة.

## 4. موضع الشنت ولماذا low-side مبدئي

- TLV3201 يعمل عند common-mode قريب من GND؛ لذلك shunt low-side أبسط من high-side 12V مع هذا comparator.
- يجب توصيل sense lines Kelvin مباشرة إلى طرفي الشنت، بعيداً عن تيار القدرة.
- Source MOSFET يقع فوق أرضي القدرة بمقدار Vshunt؛ يجب ربط driver return عند Kelvin source، والتحقق من مستويات دخل TC4420 مع هذا الانزياح والضوضاء.
- لا نمرر تيار الملف عبر مسارات comparator/MCU، ولا نستخدم أرضي إشارة طويل مشترك مع حلقة TX.
- إذا أثبتت ضوضاء source bounce عدم صلاحية low-side، ننتقل إلى high-side current-sense amplifier سريع ثم comparator، لكن لا نختار ذلك قبل مقارنة تأخير المسار كاملاً.

## 5. ميزانية زمن الاستجابة

المسار الكامل:
`Shunt → TLV3201 → asynchronous fault latch → gate-input inhibit → TC4420 turn-off → MOSFET current fall`

هدف التصميم التحليلي هو جعل المجموع دون1µs، ويفضل دون0.5µs، لكن لا يعد هذا رقماً مثبتاً. يجب جمع worst-case propagation delays من كل datasheet، وإضافة gate charge/Miller/driver sink، ثم التحقق بالراسم. نموذج `current_limit_response()` يبين أثر التأخير على current overshoot.

## 6. قرار المرشح

- TLV3201 هو comparator مرشح A للمقارنة بسبب offset 4mV max عبر الحرارة وdelay55ns max.
- 50mΩ/150mV شنت وعتبة3A مثال حسابي؛ لا تعتمد.
- لا comparator/shunt/reference/latch نهائي حتى إغلاق قيمة تيار التشغيل، عتبة fault، tolerance، الضوضاء، التوقيت، وتبريد/نبضية الشنت.

## 7. المصدر الرسمي

- TI TLV3201/TLV3202 datasheet SBOS561C: https://www.ti.com/lit/ds/symlink/tlv3201.pdf
- TI TLV3501 datasheet SBOS321E: https://www.ti.com/lit/ds/symlink/tlv3501.pdf
