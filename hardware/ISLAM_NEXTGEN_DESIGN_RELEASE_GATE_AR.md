# إغلاق التصميم الهندسي قبل إصدار أمر الشراء — ISLAM NEXTGEN

التاريخ: 2026-11-14
الفرع: `hardware/islam-nextgen-final-platform`
الحالة: **إغلاق مراجعة التصميم وتثبيت خط الأساس؛ إصدار الشراء النهائي محجوب هندسياً.**

هذه الوثيقة تحسم ما ثبت وما لا يجوز ادعاء إغلاقه. لا تعني وجود جهاز أو PCB مختبرة.

## 1. قرارات التصميم المقفلة

| البند | القرار المثبت |
|---|---|
| رأس البحث | رأس واحد فقط، حلزوني مربع مسطح 350×350mm، 13 لفة |
| سلك الرأس | نحاس مينا، قطر النحاس العاري 0.60mm، شراء حسابي 20m بعد التحقق من المورد |
| مرجع الحساب | L≈175.8µH وR≈1.064Ω عند20°C؛ قيم نظرية فقط |
| المعالج الحرج للتوقيت | STM32G474RE على NUCLEO-G474RE |
| اتصال الهاتف | ESP32-S3 N16R8 عبر UART/Wi-Fi؛ لا يحدد توقيت النبض |
| توقيت TX | HRTIM، لا software delay ولا Android/Wi-Fi |
| الحماية | COMP1/HRTIM hardware fault إلزامي؛ البرنامج ليس حماية التيار النهائية |
| الاستقبال | Mono-loop مع فصل high-gain أثناء TX/flyback؛ لا نعتمد bifilar |
| مفتاح AFE | TMUX6219 ×2 كاختيار وظيفي مرشح، مع مراجعة pin-level قبل PCB |
| وضع الرأس | لا رأس DD ولا رأس ثانٍ في هذه النسخة |

## 2. نتائج حساب الملف المعتمدة كمرجع نظري

عند 12V، L=175.8µH، R=1.064Ω:
- بلوغ 5A نظرياً ≈96.8µs.
- بلوغ 6A نظرياً ≈125.5µs.
- الطاقة المغناطيسية عند5A ≈2.20mJ.
- الطاقة المغناطيسية عند6A ≈3.16mJ.

**حد التصميم:** 5A هو نقطة ضبط/حماية أولية قصوى للنسخة الأولى، وليس تصريحاً بأن الدارة جاهزة. لا يعتمد 6A. لا يعتمد 300µs. يجب أن يوقف COMP1 نبضة TX عتادياً عند حد التيار، مع maximum-on-time مستقل كحماية ثانية.

لا يثبت تردد نبض نهائي قبل إثبات حرارة MOSFET ومسار clamp والملف. لا نضع 1kHz كقيمة شراء أو تشغيل مضمونة.

## 3. إغلاق مرحلة TX — قرار عدم اعتماد المرشحات الحالية

- طوبولوجيا low-side MOSFET مع flyback network عبر الملف هي بنية البحث الحالية.
- IRFP264PBF يبقى مرشحاً فقط؛ لا يصدر اعتماد شراء حتى يتم transient parasitic analysis وإثبات VDS peak ضمن هامش آمن وSOA وحرارة التشغيل.
- TC4420CPA يبقى مرشح gate driver؛ لا تثبت Rgate/Vdrive قبل اختيار MOSFET النهائي وتحليل Qg وسرعة الحافة.
- 3×1.5KE39CA + 47Ω + STTH112U هي فرضية نموذج فقط. لا تعتمد سلسلة TVS قبل حساب تفاوت VBR وتقاسم الجهد والحرارة المتكررة.
- لا يستخدم MOSFET avalanche كمسار flyback اعتيادي.
- shunt 10mΩ ليس نهائياً حتى تحديد مضخم القياس، Kelvin layout، قدرة النبضة، وعتبة COMP1.
- يجب أن يتضمن ملف التصميم transient parasitics: Lstray، Coss، سعة الكابل والملف، ومقاومة/محاثة الموصلات. نموذج RL/TVS الخطي الحالي ليس SPICE ولا قياساً.

**حالة TX: مغلق قرارياً (لا شراء)، غير مغلق كهربائياً.**

## 4. إغلاق AFE — تثبيت الوظائف ومنع تشبع الاستقبال

- مسار low-gain محمي يبقى للمراقبة أثناء TX/flyback.
- مسار high-gain يبقى مفصولاً حتى يؤكد COMP2/HRTIM recovery أن الجهد ضمن المجال الآمن.
- بعد التعافي، يفتح المسار العالي ثم يبدأ bucking/الطرح التفاضلي والعينات المتزامنة.
- TMUX6219 هو SPDT واحد لكل شريحة؛ EN فعّال بمستوى HIGH، وLOW يفصل S1 وS2. لذلك PB7 مع pull-down 10kΩ يبقي المفتاحين OFF أثناء reset إذا كانت قطبية التوصيل كما في الداتا شيت.
- إشارات TMUX6219 يجب أن تبقى بين VSS وVDD؛ لا يمرر أي switch عقدة flyback أو Drain.
- AD8336 يقبل تغذية ±3V إلى±12V، لكن عند تغذية أعلى من ±10V ينخفض حد حرارة التشغيل إلى +85°C. لذلك لا يعتمد TEN8-1222 ±12V كـrail مباشر. يجب اختيار rail AFE بعد حساب الحمل والتبديد؛ ±5V خيار تصميم مفضل للدراسة، لا قيمة BOM مثبتة بعد.
- لا تعتمد قيم الكسب أو clamp أو مقاومة السلسلة أو VDCb أو Rvar النهائية قبل نموذج إشارة زمني كامل وheadroom/settling/noise analysis.
- لا تعتمد OPA1612/AD8336/MCP41HV51 كقائمة شراء حتى يتأكد أن كل مرحلة تعمل ضمن common-mode/output swing والضجيج والـsettling الفعلي.

**حالة AFE: مغلق وظيفياً، غير مغلق على مستوى schematic/values.**

## 5. إغلاق التغذية

- بطارية 4S LiFePO4 وBMS 10A/15A كانت فرضية، وليست اختياراً نهائياً.
- لا يعتمد BMS أو fuse قبل حساب تيار البطارية الفعلي، تيار الإقلاع، peak current، أسلاك القدرة، تيار القصر، ووقت التشغيل.
- لا يعتمد محول ±12V AFE؛ rail AD8336 يحتاج إعادة تقييم حراري.
- يلزم فصل قدرة TX عن تغذية AFE/MCU، مع تنظيم ومرشحات وقياس undervoltage/overvoltage/temperature.
- يجب تحديد كل rails، currents، startup sequence، shutdown discharge، reverse polarity، fuse coordination، وconnector ratings في power tree قبل اختيار أرقام القطع.

**حالة التغذية: غير مغلقة؛ لا شراء بطارية/BMS/DC-DC/fuse بعد.**

## 6. إغلاق خريطة المنافذ

تظل خريطة NUCLEO-G474RE مرجعاً مبدئياً، لكن لا تصبح pinout PCB نهائياً حتى:
1. تدقيق جميع alternate functions على STM32G474RE package المحدد.
2. تدقيق solder bridges والموصلات على NUCLEO revision التي ستشترى.
3. تأكيد مسار COMP1 إلى HRTIM fault ومسار COMP2 recovery/event في إعداد HRTIM الفعلي.
4. تأكيد قياس الشنت لا يحمّل PB1 ولا يضعف comparator.
5. تدقيق active polarity لكل EN/FAULT/RESET وdefault states عند reset/brownout.

## 7. بوابة إصدار BOM النهائية

لا يمكن تسمية القائمة «نهائية للشراء» قبل إرفاق جميع الآتي في PR:
- schematic كاملة قابلة للتحرير (KiCad) لكل من power, TX, RX/AFE, MCU, ESP32, connectors.
- ERC بلا أخطاء غير مبررة، وDRC بلا أخطاء تصنيع.
- transient/SOA/thermal report للـTX والـclamp.
- AFE headroom/noise/settling report مع حالات saturation/recovery.
- power budget وbattery/BMS/fuse/connector calculations.
- BOM من KiCad تشمل Manufacturer Part Number, package, rating, quantity, approved source، وبديل واحد مطابق عند الحاجة.
- مراجعة pinout والموصلات والـtest points وطرق الاختبار الذاتي.
- مراجعة مستقلة للمخطط قبل إصدار Gerbers أو أمر الشراء.

## 8. ما تم التحقق منه آلياً

على commit `b9058902f3ee12df8dbe194ab29f9662a6cefd67` نجحت:
- PI model checks: https://github.com/Khaledserdani/IslamDetector/actions/runs/43593134927
- Android app CI: https://github.com/Khaledserdani/IslamDetector/actions/runs/43593134983

هذا لا يعادل محاكاة SPICE، ولا قياساً على PCB، ولا اختباراً ميدانياً.

## 9. أمر التنفيذ

الوثائق الحالية تعتبر **خط أساس هندسي مجمداً** وليست إذناً بالشراء. الخطوة التالية في المشروع هي إنشاء schematic KiCad كاملة على هذا الخط، وتشغيل ERC/DRC والمحاكاة والتحقق الحراري، ثم توليد BOM واحدة. لا يُطلب من المستخدم شراء أجزاء مرشحة أو لحام SMD يدوياً.
