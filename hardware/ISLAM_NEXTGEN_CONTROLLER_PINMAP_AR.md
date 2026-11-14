# خريطة منافذ وحدة التحكم — ISLAM NEXTGEN / NUCLEO-G474RE

التاريخ: 2026-11-14
الفرع: hardware/islam-nextgen-final-platform
الحالة: توزيع أولي للمنافذ من داتا شيت ST ودليل اللوحة؛ لا توصيل للقدرة قبل مخطط الحماية النهائي.

## 1. وحدة التحكم المرجعية

اللوحة المحددة: NUCLEO-G474RE، المتحكم STM32G474RE.
- HRTIM1 لتوليد توقيت TX بدقة عتادية.
- ADC1+ADC2 في regular simultaneous mode.
- DMA لنقل العينات.
- ST-LINK مدمج للبرمجة والتصحيح.
- وحدة Wi-Fi منفصلة على UART؛ لا نحمّل اتصال الهاتف توقيت النبضة.

المراجع:
- ST NUCLEO-G474RE: https://www.st.com/en/evaluation-tools/nucleo-g474re
- ST UM2505: https://www.st.com/resource/en/user_manual/dm00556337.pdf
- STM32G474 datasheet: https://www.st.com/resource/en/datasheet/stm32g474mb.pdf
- STM32G4 RM0440: https://www.st.com/resource/en/reference_manual/dm00355726.pdf

## 2. المنافذ المحجوزة

| الوظيفة | منفذ MCU | قناة/وظيفة بديلة | موصل اللوحة | الحالة |
|---|---|---|---|---|
| قياس إشارة الملف بعد AFE | PA0 | ADC1_IN1 | CN8-1 / Arduino A0 | مرشح أول |
| قياس مرجع/قناة مراقبة متزامنة | PA1 | ADC2_IN2 | CN8-2 / Arduino A1 | مرشح أول |
| خرج توقيت TX الأساسي | PA8 | HRTIM1_CHA1 (AF13) | CN9 pin 8 (D7) وCN10 pin 23 | مرشح أول |
| خرج تشغيل مفتاح مرجع bucking SWb | PA9 | HRTIM1_CHA2 (AF13) | Arduino D8 / CN5 pin 1 وCN10 pin 21 | تشغيل SWb متزامن مع TX-off |
| إيقاف عتادي سريع | PA12 | HRTIM1_FLT1 | Morpho CN10 pin 12 | مرشح أول |
| UART إلى وحدة Wi-Fi | PB10 | USART3_TX (AF7) | Morpho CN10 pin 25 | مرشح أول |
| UART من وحدة Wi-Fi | PB11 | USART3_RX (AF7) | Morpho CN10 pin 18 | مرشح أول |
| ناقل I²C لحساسات الطاقة/الحرارة | PB8/PB9 | I2C1 SCL/SDA | Arduino D15/D14 | احتياطي |
| SPI احتياطي لوحدة ADC خارجية/تخزين | PA5/PA6/PA7 | SPI1 SCK/MISO/MOSI | Arduino D13/D12/D11 | احتياطي |

## 3. نقاط تدقيق

- PA0 وPA1 مدخلان سريعان من مجموعة ADCx_IN1..IN5، ويمكن ضبط ADC1 على IN1 وADC2 على IN2 مع أخذ عينتين متزامنتين. لا تستخدم PA4 كبديل سريع؛ PA4 هو ADC2_IN17 ويقع ضمن slow channels.
- PA8/PA9 يدعمان HRTIM1_CHA1/CHA2 وفق جدول alternate functions. نستخدم HRTIM كمصدر توقيت لا software GPIO toggling.
- PA12 يحمل HRTIM1_FLT1، ويجب أن يُستخدم كمسار حماية عتادي إذا ثبتت ملاءمة التوصيل؛ يمكن أن يأتي fault من comparator أو دائرة overcurrent مستقلة.
- PB10/PB11 يدعمان USART3، وهما منفصلان عن PA8/PA9 المخصصين للتوقيت.
- PB8/PB9 يمكن حجزهما لـI²C لمراقبة البطارية والتيار/الحرارة، مع تجنب تعارضات أي لوحة توسعة.
- SPI يبقى احتياطياً، وليس مطلوباً في baseline إذا استخدمنا ADC الداخلي.

## 4. قيود لا تزال قبل المخطط النهائي

1. مراجعة كامل pinout والـsolder bridges للوحة MB1367 revision التي ستُشترى.
2. التأكد من أن موصلات Nucleo تأتي مركبة/ملحومة مسبقاً أو تحديد shield مصنعياً يركب دون لحام يدوي.
3. حساب مستويات منطق Gate Driver وWi-Fi UART والتغذية المشتركة.
4. اختيار مدخل fault الفعلي ومصدره (comparator/overcurrent) وتأكيد أن الاستجابة hardware fault تمنع نبضة TX في الزمن المطلوب.
5. اختيار القنوات الإضافية لمراقبة تيار TX وجهد البطارية وحرارة MOSFET بعد تثبيت دارة القياس.
6. منع أي اتصال مباشر بين منافذ MCU والملف أو drain MOSFET أو عقدة الجهد النبضي.

## 5. قرار أولي

هذه الخريطة تجعل وحدة التحكم قابلة للتوصيل إلى لوحة AFE/TX مصنعة مسبقاً عبر shield أو ضفيرة مقفلة، وتترك Wi-Fi منفصلاً. لا تُعد pinout نهائياً للـPCB قبل مراجعة ملفات التصنيع والسكيما الخاصة بإصدار NUCLEO-G474RE الذي سيُستخدم.


## 6. منافذ AFE بعد اعتماد time-domain bucking

بعد تحديث قرار الاستقبال، تضاف المنافذ التالية:
| الوظيفة | منفذ MCU | موصل اللوحة | الملاحظة |
|---|---|---|---|
| DAC لضبط سعة bucking | PA4 / DAC1_OUT1 | Arduino A2 / CN8 pin 3 | خرج DAC إلى buffer AFE |
| SPI clock للمقاومة الرقمية | PA5 / SPI1_SCK | CN5 pin 6 / D13 | MCP41100 |
| SPI data إلى المقاومة الرقمية | PA7 / SPI1_MOSI | CN5 pin 4 / D11 | MCP41100؛ لا يحتاج MISO |
| CS للمقاومة الرقمية | PB6 / GPIO | CN5 pin 3 / D10 وCN10 pin 17 | Chip select |
| ADC1 إشارة الفرق | PA0 / ADC1_IN1 | A0 / CN8 pin 1 | القناة الأساسية |
| ADC2 مراقبة bucking | PA1 / ADC2_IN2 | A1 / CN8 pin 2 | متزامنة مع ADC1 |

**تدقيق موصلات:** وفق جدول UM2505:
- PA12 على CN10 pin 12.
- PB10 على CN10 pin 25.
- PB11 على CN10 pin 18.
- PA8 على CN10 pin 23.
- PA9 على CN10 pin 21.
- PA5/PA6/PA7 على CN5 pins 6/5/4.
- PB6 على CN5 pin 3 وCN10 pin 17.
- PA4 على A2 / CN8 pin 3.

المصدر الرسمي:
https://www.st.com/resource/en/user_manual/dm00556337.pdf


## 7. التوزيع النهائي الأولي لمقارنات الحماية وواجهة AFE

بعد تدقيق مصفوفة الربط الداخلية في RM0440، يمكن استخدام المقارنات وDACs الداخلية دون استهلاك أرجل إضافية:
- **COMP1**: مدخل موجب PB1 لقياس shunt تيار TX، ومدخل سالب DAC3_CH1 الداخلي كعتبة تيار. خرج COMP1 يربط داخلياً بمدخل HRTIM fault؛ لا يلزم إخراجه على PA0/PA6.
- **COMP2**: مدخل موجب PA7 لقياس envelope في مسار الاستقبال منخفض الكسب، ومدخل سالب DAC3_CH2 الداخلي كعتبة recovery. خرجه يربط بحدث HRTIM خارجي داخلياً.
- **DAC1_CH1 على PA4/A2**: ضبط سعة مرجع bucking.
- **DAC3_CH1 وDAC3_CH2**: عتبتا COMP1/COMP2 داخلياً، ولا تحتاجان أرجل GPIO.
- **SPI2** للمقاومة الرقمية MCP41100: PB13=SCK على CN10 pin30، PB15=MOSI على CN10 pin26، وPB6=CS على D10/CN10 pin17. لا يحتاج MCP41100 خط MISO.
- **PA12 / CN10 pin12**: مدخل زر إيقاف/Interlock خارجي مستقل، إضافة إلى مسار المقارن الداخلي.

هذا يترك PA3 حراً ولا يتعارض مع LPUART1/VCP المدمج على اللوحة. ويترك PA5/PA6/PA7 خارج SPI1؛ PA7 مستخدم الآن كمدخل COMP2 فقط.

المراجع:
- RM0440 Table 72: DAC outputs to COMP1/2; DAC3 internal.
- RM0440 Table 73: COMP1/2 pin inputs and DAC3 thresholds.
- RM0440 §11.3.9: comparator outputs can connect internally to HRTIM external events and fault inputs.
- UM2505 Table 16/17: PB1, PA7, PB13, PB15, PB6, PA12 connector mapping.
https://www.st.com/resource/en/reference_manual/dm00355726.pdf
https://www.st.com/resource/en/user_manual/dm00556337.pdf
