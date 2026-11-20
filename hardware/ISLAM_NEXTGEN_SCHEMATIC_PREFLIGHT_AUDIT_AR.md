# تدقيق ما قبل رسم Schematic — ISLAM NEXTGEN
التاريخ: 2026-11-14
الفرع: hardware/islam-nextgen-final-platform
الحالة: تدقيق اتساق إلزامي قبل إنشاء مخطط كهربائي قابل للتصنيع.

## النتيجة التنفيذية
تمت مراجعة وثائق release gate وarchitecture وreceiver وAFE وpinmap وADC وTX. لا يجوز حالياً تحويلها مباشرة إلى schematic شراء؛ توجد تناقضات/فجوات تؤثر في قيم الدارة وتوصيلاتها. هذا الملف يسجل نقاط الإيقاف بدقة كي لا نرسم دائرة تبدو مكتملة بينما تحمل افتراضات متعارضة.

## 1. مواصفة رأس البحث — أُغلقت وثائقياً
- وثيقة الملف hardware/ISLAM_NEXTGEN_SINGLE_SPIRAL_COIL_AR.md هي المرجع الحالي: رأس واحد Planar square spiral، 350×350mm على خط مركز اللفة الخارجية، 13 لفة، نحاس مينا بقطر نحاس عارٍ 0.60mm، pitch 1.20mm.
- أضيف تصحيح لاحق إلى receiver decision وarchitecture ينص صراحة أن هذا القرار يعلو على العبارات الأقدم التي أبقت الأبعاد مفتوحة أو تحدثت عن رأسين قابلين للتبديل.
- طول النحاس النظري 17.4512m، شراء حسابي 20m، L≈175.8µH وR≈1.064Ω عند20°C؛ لا تزال قيماً نظرية حتى قياس الملف والكابل.
**الحالة:** التعارض الوثائقي أُغلق. تبقى القياسات المادية بعد تصنيع الرأس، ولا يمنع هذا البند رسم موصل الرأس.

## 2. تعارض جهد تغذية AFE — مانع اختيار القطع
- بعض الأقسام القديمة في AFE وpinmap تفترض ±12V_AFE مباشرة لـTMUX6219 وMCP41HV51 وAD8336.
- تدقيق AD8336 Rev.G أثبت أن التشغيل ±10V إلى ±12V يخفض حد الحرارة إلى +85°C؛ كما أن TEN8-1222 ±12V لم يعتمد كمصدر مباشر.
- release gate يمنع اعتماد ±12V مباشرة ويطلب تحديد rail بعد headroom/thermal analysis؛ ±5V اتجاه دراسة وليس قيمة معتمدة.
**الإجراء المطلوب:** تحديد rail لكل IC على حدة، وحسم هل AD8336 سيعمل على ±5V أو rail آخر، وإعادة تدقيق common-mode وswing والتحكم GPOS/GNEG. لا تكتب ±12V_AFE كشبكة تغذية نهائية في schematic قبل هذا القرار.

## 3. مسار bucking غير مكتمل كدائرة قابلة للرسم
المبدأ مثبت: VDCb مستقل + SWb + gyrator + VGA + differential subtraction. لكن الوثائق لا تثبت بعد:
- طوبولوجيا gyrator الدقيقة (المخطط/العقد/اتجاه التيار) بعد إعادة البناء.
- مصدر VDCb وقيمته وحدود تياره وتسلسله عند startup.
- طريقة توصيل SWb على شبكة الجيريتور مع TMUX6219 دون تحميل أو حقن transient في مفاتيح الإشارة.
- اختيار AD8336 أو البديل، ومجال التحكم بعد attenuator.
- قيم feedback/compensation للمضخمات وممانعات المصدر/الحمل.
**الإجراء المطلوب:** نقل الدائرة المرجعية إلى schematic مرقمة العقد، ثم تحليل transient/settling قبل تثبيت قيم R/C.

## 4. مسار حماية RX والـblanking غير محدد كمياً
- low-gain monitor يبقى متصلاً، وhigh-gain path يفصل أثناء TX/flyback.
- لا توجد حتى الآن قيم مقاومة السلسلة أو clamp voltage/charge budget أو تيار الحقن المسموح.
- BAV99 مرشح فقط؛ لا يوجد مسار امتصاص clamp محسوب، ويحظر حقن تيار غير محسوب إلى 3.3V أو ±AFE.
- TMUX6219 لا يمرر عقدة Drain أو flyback؛ يجب أن تكون عقد S1/S2/D ضمن VSS..VDD في جميع الأوضاع.
**الإجراء المطلوب:** نموذج جهد/تيار عند مدخل كل مرحلة، تحديد clamp topology ومصرف الشحنة، ثم إثبات عدم تجاوز absolute maximum وعدم بقاء clamp موصلاً أثناء قراءة الإشارة الصغيرة.

## 5. حماية TX ليست مغلقة كهربائياً
- IRFP264PBF وTC4420CPA و3×1.5KE39CA و47Ω وSTTH112U كلها مرشحات لا شراء.
- نموذج TVS الحالي ليس SPICE ولا يتضمن Lstray/Coss/Ccable أو منحنى TVS الحراري أو SOA.
- شرط VDS peak ≤200V على MOSFET 250V يبقى معيار تصميم أولياً، ولا توجد محاكاة parasitic أو قياسات تثبته.
- shunt 10mΩ والـamplifier/COMP1 threshold وKelvin routing غير محددة كمياً.
**الإجراء المطلوب:** إكمال شبكة TX/clamp مع transient model parasitic وSOA/thermal report؛ لا يطلق PCB أو BOM قبل ذلك.

## 6. تدقيق واجهات STM32 — نقاط يجب تثبيتها داخل المخطط
- PA0/ADC1_IN1 وPA1/ADC2_IN2: زوج القياس السريع المقترح.
- PA8/HRTIM1_CHA1: TX gate-driver command.
- PA9/HRTIM1_CHA2: SWb select/control.
- PA10/HRTIM1_CHB1: high-gain blanking select/control.
- PB7: TMUX6219 EN المشترك، active-HIGH، مع pull-down 10kΩ إلى DGND؛ default-off.
- PB1: COMP1_INP وADC1_IN12 لقياس الشنت بعد تكييف؛ يجب ألا يحمّل comparator.
- PA7: COMP2_INP recovery envelope.
- PA4/PA5: DAC1 outputs، وليسا قناتي ADC سريعتين.
- PB13/PB15/PB6: SPI2 SCK/MOSI/CS للمقاومة الرقمية إن بقيت MCP41HV51.
- PB10/PB11: USART3 إلى ESP32-S3.
- يلزم تدقيق أخير للـalternate functions وsolder bridges وموصلات NUCLEO-G474RE revision الفعلية قبل تثبيت symbols/connector pin numbers.

## 7. Power tree غير مكتمل
لا توجد مواصفات محسومة للبطارية/BMS/fuse/DC-DC أو rail sequencing. كما لا يوجد قرار نهائي بشأن هل لوحة NUCLEO وESP32 ستغذيان من 5V واحد أم فروع منفصلة مع حماية. يجب أن يشمل power tree:
- مصدر البطارية، الحماية، فصل TX عن AFE/logic.
- 5V/3.3V logic، rails AFE الموجبة والسالبة، ومرجع 1.65V.
- UVLO/OVLO، reverse polarity، current limits، startup/shutdown discharge.
- مراقبة تيار البطارية والجهود والحرارة.
لا يجوز اختراع قيم تيار أو قدرة أو fuse قبل إغلاق ميزانية الطاقة.

## 8. أدوات التحقق المتاحة في جلسة العمل
- تم فحص بيئة التنفيذ الحالية: لا يظهر KiCad CLI ولا ngspice مثبتين.
- لذلك لم يتم تشغيل ERC/DRC أو SPICE في هذه الجلسة، ولا يجوز وصف أي مخطط بأنه اجتازها.
- يمكن إنشاء وثيقة schematic/netlist مواصفاتية ومراجعتها نصياً، لكن ذلك لا يعادل ملف KiCad قابل للتحرير أو محاكاة كهربائية.
**الإجراء المطلوب:** توفر بيئة KiCad/ngspice أو مسار تنفيذ يدعم إنشاء ملفات KiCad ثم تشغيل ERC/DRC وSPICE فعلياً. لا يتم الادعاء بأن ذلك قد حدث قبل رؤية مخرجات الأدوات.

## 9. بوابة الانتقال إلى schematic قابلة للتصنيع
لا تبدأ schematic النهائية إلا بعد إغلاق:
1. مواصفة الرأس المرجعية وتطابق الوثائق.
2. rails AFE لكل IC، مع تحليل حراري.
3. gyrator/VDCb/SWb/VGA topology وعقدها.
4. RX clamp/blanking ومجال كل عقدة.
5. TX clamp وMOSFET/driver/shunt مع SOA/transient/thermal.
6. power tree وتسلسل الإقلاع والإطفاء.
7. مراجعة pinout/connector/footprints على NUCLEO-G474RE.

بعد ذلك تُنشأ ملفات KiCad: schematic متعددة الصفحات، symbols/footprints، BOM، ثم ERC/DRC وSPICE. أي قطعة غير محسومة تبقى DNP/placeholder في نسخة التطوير ولا تتحول إلى أمر شراء.

## الحكم
**المشروع تقدم إلى مرحلة pre-schematic audit.** لا توجد schematic كاملة قابلة للتصنيع بعد، ولا BOM شراء نهائية، ولا دليل عتادي. هذه ليست إعادة فتح للقرارات المحسومة؛ إنها إزالة تعارضات تمنع تحويلها إلى توصيلات آمنة.


## 10. تحديث بعد تسوية مواصفة الملف
تمت تسوية تعارض هندسة الرأس في وثيقتي receiver decision وarchitecture. مواصفة 350×350mm/13 turns مثبتة كـgeometry baseline، ولم تعد مانعاً لرسم الموصل. الموانع الفعلية المتبقية هي rail AFE، gyrator/VDCb/SWb، RX protection/blanking، TX transient/SOA/thermal، وpower tree.
