> **حدود التطبيق — 2026-11-19:** أمثلة 50mΩ/150mV/3A ونماذج L=50µH أو R=0.9Ω حسابات توضيحية/حالات stress وليست عتبة معتمدة لـDD32. لا تختَر الشنت أو comparator قبل قياس DD32 L/DCR وطوبولوجيا TX وتحديد تيار التشغيل الأقصى مع زمن القطع والـovershoot.

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


## 8. Fault latch مرشح A — SN74LVC2G74
أضيفت REV_A_TX_FAULT_LATCH_CANDIDATES_AR.md. المرشح SN74LVC2G74 بمدخلي PRE/CLR غير متزامنين active-low؛ PRE_N منخفض يثبت Q=FAULT، وCLR_N منخفض يمسح فقط بعد تحقق RESET_REQUEST + STOP_OK + OC_CLEAR_N + RESET_N. TPS3808 supervisor يفرض POR/brownout إلى PRE_N، وTLV3201 OC عبر SN74LVC1G04 وSN74LVC1G08 يثبت fault. Qbar=NOT_FAULT يدخل بوابة TX النهائية. لا يجوز reset تلقائي أو reset أثناء overcurrent. ما زال threshold supervisor وreset gating والـfault injection مفتوحاً.


## 9. اختيار شنت Kelvin فعلي مرشح — Littelfuse L4CL-A

### 9.1 المرشح A
Littelfuse L4CL2512LR050FYR-A:
- 50mΩ، ±1%، 1W، TCR±30ppm/°C، package2512، أربع أطراف Kelvin.
- داتا شيت L4CL-A تصفه Four-Terminal/Kelvin sensing مع separate voltage-sensing terminals وlow ESL.
- عند3A: Vshunt=150mV، P=I²R=0.45W، أي أقل من rating1W عند شروط الداتا شيت. الحد المحافظ لطاقة نبضة20µs إذا افترضنا3A طوال النبضة=9µJ؛ عند100Hz متوسطها الأعلى النظري0.9mW.
- offset TLV3201 max4mV يعادل80mA عبر50mΩ. مع شنت±1% ومرجع150mV±1%، trip النظري≈2.86–3.14A قبل noise/hysteresis/Kelvin error وتأخير القطع.

### 9.2 مقارنة القيم
| الشنت | الإشارة عند3A | القدرة عند3A | أثر offset4mV | التقييم |
|---|---:|---:|---:|---|
| 30mΩ | 90mV | 0.27W | 133mA | فقد أقل لكن حساسية offset أسوأ |
| **50mΩ** | **150mV** | **0.45W** | **80mA** | أفضل توازن مبدئي |
| 100mΩ | 300mV | 0.90W | 40mA | هبوط/حرارة أعلى ويقترب من1W rating |

### 9.3 طريقة التوصيل
- أطراف القدرة في مسار MOSFET source إلى PGND فقط.
- طرفا Kelvin يذهبان مباشرة إلى مدخلي comparator، دون مرور تيار القدرة في مسارات sense.
- اجعل مسار Kelvin زوجياً ومتقارباً، بعيداً عن Drain/Gate وloop TX.
- لا توصل sense إلى أرجل القدرة بعد مسارات نحاسية طويلة؛ لا تستخدم ground trace مشتركاً.

### 9.4 قرار العتبة
150mV يقابل3A nominal، وهو مثال التصميم السابق. لا نثبت قيمة المرجع أو trip حتى حساب source bounce والضوضاء وoffset المرجع ووقت comparator→latch→driver. يجب أن يبقى مجموع زمن القطع الفعلي دون1µs (هدف دون0.5µs)، ثم يعاد حساب overshoot على Lmin=50µH وRmin=0.9Ω كحالة stress محافظة.

**القرار:** L4CL2512LR050FYR-A هو مرشح A للشنت بسبب Kelvin 4-terminal و1W و±1%، وليس اعتماد شراء بعد. لا يزال قياس الضوضاء/الحرارة/النبضة والـlayout مطلوباً.

المصدر الرسمي: Littelfuse L4CL-A Series datasheet: https://www.littelfuse.com/assetdocs/littelfuse-resistor-l4cl-a-datasheet?assetguid=a57275e4-80b6-41b0-ab69-386df0e05ecf


**حالة الاعتماد:** لا يعتمد comparator أو الشنت بعد؛ تبقى قيم العتبة والشنت والمرجع والـlatch مفتوحة حتى قياس DD32 وحساب worst-case للتيار والـovershoot والتحقق بالراسم. أمثلة 50mΩ/3A ليست مواصفة شراء أو تشغيل.
