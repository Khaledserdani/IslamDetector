# تصميم مرشح Fault Latch عتادي لمرحلة TX — Rev A

**الحالة:** مرشح A وظيفي مع منطق إشارات محدد؛ ليس schematic نهائياً ولا BOM شراء.  
**التاريخ:** 2026-11-18

## 1. الوظيفة المطلوبة
- أي تجاوز تيار من TLV3201 يثبت FAULT فوراً، حتى بعد هبوط التيار.
- لا يعاد تشغيل TX تلقائياً عندما يزول تجاوز التيار.
- لا يمسح fault إلا بأمر RESET يدوي، بشرط STOP وغياب overcurrent وصلاحية التغذية.
- أثناء startup أو انخفاض 3.3V، يكون FAULT مفعلاً وTX ممنوعاً.
- خرج اللاتش يذهب إلى AND gate النهائي كإشارة NOT_FAULT، وإلى ESP32 للعرض/التسجيل فقط.

## 2. المرشحون

| الوظيفة | المرشح | بيانات موثقة | القرار |
|---|---|---|---|
| Fault latch | TI SN74LVC2G74 | 1.65–5.5V؛ PRE وCLR غير متزامنين active-low؛ PRE منخفض يثبت Q=1، CLR منخفض يمسح Q=0؛ tPD max5.9ns عند3.3V | مرشح A |
| Supervisor / POR | TI TPS3808G01 (adjustable) أو G33 | RESET open-drain active-low؛ delay1.25ms–10s؛ G33 threshold3.07V، G01 adjustable threshold0.405V | مرشح A للدراسة؛ لا تثبيت threshold قبل اختيار منظم3.3V |
| 5V-to-3.3V logic inversion | TI SN74LVC1G04 | VCC1.65–5.5V؛ input tolerant حتى5.5V؛ tPD max3.3ns عند3.3V | مرشح A لتحويل OC_FAULT 5V إلى active-low |
| AND logic | TI SN74LVC1G08 | 1.65–5.5V؛ tPD max3.6ns عند3.3V؛ input tolerant حتى5.5V | مرشح A للبوابة المنطقية |

## 3. منطق اللاتش المقترح

التعريفات:
- OC_FAULT = 1 عندما TLV3201 يكتشف overcurrent (خرج push-pull على تغذية5V).
- OC_CLEAR_N = NOT(OC_FAULT)، عبر SN74LVC1G04 على تغذية3.3V؛ دخل LVC يقبل حتى5.5V.
- RESET_N = خرج TPS3808 open-drain، مع pull-up إلى3.3V؛ يكون LOW أثناء POR أو انخفاض rail.
- PRE_N = RESET_N AND OC_CLEAR_N، عبر SN74LVC1G08.
- CLR_N = NOT(RESET_REQUEST AND STOP_OK AND OC_CLEAR_N AND RESET_N)، أي لا يسمح بالمسح إلا إذا كان RESET اليدوي مطلوباً، وSTOP فعال، ولا يوجد overcurrent، وrail صالح.
- D=0 وCLK=GND على SN74LVC2G74 (تثبيت المدخلات غير المستخدمة، لا clock software).
- Q = FAULT_LATCH؛ Qbar = NOT_FAULT.

سلوك الحالات:
1. **Power-up / brownout:** RESET_N LOW → PRE_N LOW → Q=1 (FAULT) → Qbar=0 (TX inhibit).
2. **Overcurrent:** OC_FAULT HIGH → OC_CLEAR_N LOW → PRE_N LOW → Q=1 فوراً، دون انتظار clock.
3. **بعد زوال overcurrent:** OC_CLEAR_N يعود HIGH لكن Q يبقى1؛ لا إعادة تشغيل تلقائية.
4. **مسح يدوي:** فقط مع STOP_OK=1 وOC_CLEAR_N=1 وRESET_N=1 وRESET_REQUEST=1، يصبح CLR_N LOW فيُمسح Q.
5. **أي شرط غير مؤكد أو إشارة عائمة:** يجب أن تبقي CLR_N HIGH وNOT_FAULT LOW؛ تعتمد المقاومات الافتراضية على الرسم النهائي.

يجب منع PRE_N وCLR_N من أن يكونا LOW في الوقت نفسه؛ منطق CLR_N أعلاه يتضمن OC_CLEAR_N وRESET_N لمنع ذلك. لا يجوز وصل زر RESET مباشرة إلى CLR دون شروط السماح.

## 4. مسار الحماية

TLV3201 OC output → LVC1G04 → OC_CLEAR_N → PRE_N of LVC2G74

TPS3808 RESET_N + OC_CLEAR_N → LVC1G08 → PRE_N

SN74LVC2G74 Qbar (NOT_FAULT) → final TX AND gate

final TX gate = SHOT_WINDOW AND NOT(COOLDOWN_OUT) AND ARM_OK AND POWER_GOOD AND WATCHDOG_OK AND OC_CLEAR_N AND NOT_FAULT

- Comparator يثبت fault asynchronous.
- Latch يمنع إعادة التشغيل عند تذبذب التيار حول العتبة.
- MCU يقرأ Q فقط؛ لا يستطيع مسح fault أو فرض NOT_FAULT.
- TC4420 IN وGate يجب أن يكون لهما pull-down مستقل حتى عند فقد تغذية المنطق.

## 5. حدود لم تُغلق
- اختيار TLV3201 supply rail والـoutput swing الفعلي مع 3.3V LVC input؛ داتا شيت comparator تثبت push-pull، ويجب قياس VOH/VOL تحت الحمل.
- اختيار TPS3808 threshold الصحيح بناءً على min/max لمنظم3.3V، لا نستخدم G33 تلقائياً إذا كان حد rail الأدنى أعلى من3.07V.
- تحديد منطق RESET_BUTTON/STOP_OK وdebounce ومنع reset أثناء TX.
- اختبار power-up/brownout وsimultaneous PRE/CLR ومنع metastability/false clear.
- اختبار fault injection: OC_FAULT أثناء النبضة، fault ثابت، reset أثناء fault، فقد تغذية latch/supervisor، وعودة التغذية.
- تصميم fail-safe إذا تعطلت بوابة AND النهائية أو driver؛ اللاتش وحده لا يحمي من shorted MOSFET أو driver output stuck-high.

## 6. المراجع الرسمية
- TI SN74LVC2G74 Rev.Q: https://www.ti.com/lit/ds/symlink/sn74lvc2g74.pdf
- TI TPS3808 Rev.N: https://www.ti.com/lit/ds/symlink/tps3808.pdf
- TI SN74LVC1G04 Rev.AF: https://www.ti.com/lit/ds/symlink/sn74lvc1g04.pdf
- TI SN74LVC1G08 Rev.AA: https://www.ti.com/lit/ds/symlink/sn74lvc1g08.pdf
- TI TLV3201 Rev.C: https://www.ti.com/lit/ds/symlink/tlv3201.pdf

**القرار:** SN74LVC2G74 + TPS3808 supervisor + LVC logic هي بنية مرشحة A للـfault latch. لا قيم نهائية ولا شراء حتى حسم منظم3.3V، reset gating، وfault-injection tests.


## 7. مسار قطع مباشر موازٍ للـlatch
إضافة مهمة: يجب إدخال OC_CLEAR_N نفسه مباشرة في AND gate النهائي، إلى جانب NOT_FAULT من SN74LVC2G74. بذلك يقطع comparator المسار فوراً حتى لو تأخر أو تعطل latch، بينما يبقى latch مثبتاً بعد زوال OC. المعادلة النهائية: TX_DRIVER_IN = SHOT_WINDOW AND NOT(COOLDOWN_OUT) AND ARM_OK AND POWER_GOOD AND WATCHDOG_OK AND OC_CLEAR_N AND NOT_FAULT. لا تجعل latch المسار الوحيد لقطع التيار.
