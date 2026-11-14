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
| خرج توقيت TX الأساسي | PA8 | HRTIM1_CHA1 (AF13) | CN9 pin 8 (D7) | مرشح أول |
| خرج تشغيل مفتاح مرجع bucking SWb | PA9 | HRTIM1_CHA2 (AF13) | Arduino D8 / CN5 pin 1 | تشغيل SWb متزامن مع TX-off |
| إيقاف عتادي سريع | PA12 | HRTIM1_FLT1 | Morpho CN10 pin 11 | مرشح أول |
| UART إلى وحدة Wi-Fi | PB10 | USART3_TX (AF7) | Morpho CN9 pin 7 | مرشح أول |
| UART من وحدة Wi-Fi | PB11 | USART3_RX (AF7) | Morpho CN10 pin 17 | مرشح أول |
| BOOT0 لتحديث STM32 عبر ESP32 | PB8 | BOOT0 | CN7 pin 7 / CN5 D15 | محجوز؛ لا يستخدم I²C1 |
| DAC1_CH2 للتحكم التفاضلي في AD8336 | PA5 | DAC1_OUT2 | CN5 pin 6 / Arduino D13 | مرشح أول |
| COMP2 لمراقبة recovery envelope | PA7 | COMP2_INP | CN5 pin 4 / Arduino D11 | مرشح أول |
| SPI1 | PA5/PA6/PA7 | SPI1 SCK/MISO/MOSI | — | غير متاح؛ الأرجل محجوزة للـDAC/COMP |


## 3. نقاط تدقيق

- PA0 وPA1 مدخلان سريعان من مجموعة ADCx_IN1..IN5، ويمكن ضبط ADC1 على IN1 وADC2 على IN2 مع أخذ عينتين متزامنتين. لا تستخدم PA4 كبديل سريع؛ PA4 هو ADC2_IN17 ويقع ضمن slow channels.
- PA8/PA9 يدعمان HRTIM1_CHA1/CHA2 وفق جدول alternate functions. نستخدم HRTIM كمصدر توقيت لا software GPIO toggling.
- PA12 يحمل HRTIM1_FLT1، ويجب أن يُستخدم كمسار حماية عتادي إذا ثبتت ملاءمة التوصيل؛ يمكن أن يأتي fault من comparator أو دائرة overcurrent مستقلة.
- PB10/PB11 يدعمان USART3، وهما منفصلان عن PA8/PA9 المخصصين للتوقيت.
- PB8 محجوز كخيار BOOT0 ولا يستخدم لـI²C في هذا التصميم؛ يمكن دراسة PB9 لوظيفة مستقلة بعد مراجعة التوصيلات.
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
| DAC1_CH1 للتحكم التفاضلي في AD8336 | PA4 / DAC1_OUT1 | Arduino A2 / CN8 pin 3 | عبر attenuator/RC إلى GPOS/GNEG |
| SPI clock للمقاومة الرقمية | PB13 / SPI2_SCK | CN10 pin 29 | MCP41100 |
| SPI data إلى المقاومة الرقمية | PB15 / SPI2_MOSI | CN10 pin 25 | MCP41100؛ لا يحتاج MISO |
| CS للمقاومة الرقمية | PB6 / GPIO | CN5 pin 3 / D10 | Chip select |
| ADC1 إشارة الفرق | PA0 / ADC1_IN1 | A0 / CN8 pin 1 | القناة الأساسية |
| ADC2 مراقبة bucking | PA1 / ADC2_IN2 | A1 / CN8 pin 2 | متزامنة مع ADC1 |

**تدقيق موصلات:** وفق جدول UM2505:
- PA12 على CN10 pin 11.
- PB10 على CN9 pin 7.
- PB11 على CN10 pin 17.
- PA8 على CN9 pin 8.
- PA9 على CN5 pin 1.
- PA5/PA6/PA7 على CN5 pins 6/5/4.
- PB6 على CN5 pin 3.
- PA4 على A2 / CN8 pin 3.

المصدر الرسمي:
https://www.st.com/resource/en/user_manual/dm00556337.pdf


## 7. التوزيع النهائي الأولي لمقارنات الحماية وواجهة AFE

بعد تدقيق مصفوفة الربط الداخلية في RM0440، يمكن استخدام المقارنات وDACs الداخلية دون استهلاك أرجل إضافية:
- **COMP1**: مدخل موجب PB1 لقياس shunt تيار TX، ومدخل سالب DAC3_CH1 الداخلي كعتبة تيار. خرج COMP1 يربط داخلياً بمدخل HRTIM fault؛ لا يلزم إخراجه على PA0/PA6.
- **COMP2**: مدخل موجب PA7 لقياس envelope في مسار الاستقبال منخفض الكسب، ومدخل سالب DAC3_CH2 الداخلي كعتبة recovery. خرجه يربط بحدث HRTIM خارجي داخلياً.
- **DAC1_CH1 على PA4/A2**: ضبط سعة مرجع bucking.
- **DAC3_CH1 وDAC3_CH2**: عتبتا COMP1/COMP2 داخلياً، ولا تحتاجان أرجل GPIO.
- **SPI2** للمقاومة الرقمية MCP41100: PB13=SCK على CN10 pin 29، PB15=MOSI على CN10 pin 25، وPB6=CS على D10/CN5 pin3. لا يحتاج MCP41100 خط MISO.
- **PA12 / CN10 pin11**: مدخل زر إيقاف/Interlock خارجي مستقل، إضافة إلى مسار المقارن الداخلي.

هذا يترك PA3 حراً ولا يتعارض مع LPUART1/VCP المدمج على اللوحة. ويترك PA5/PA6/PA7 خارج SPI1؛ PA7 مستخدم الآن كمدخل COMP2 فقط.

المراجع:
- RM0440 Table 72: DAC outputs to COMP1/2; DAC3 internal.
- RM0440 Table 73: COMP1/2 pin inputs and DAC3 thresholds.
- RM0440 §11.3.9: comparator outputs can connect internally to HRTIM external events and fault inputs.
- UM2505 Table 16/17: PB1, PA7, PB13, PB15, PB6, PA12 connector mapping.
https://www.st.com/resource/en/reference_manual/dm00355726.pdf
https://www.st.com/resource/en/user_manual/dm00556337.pdf


## 8. BOOT0 وتحديث الهاتف

- PB8 / BOOT0 على CN7 pin 7 / CN5 D15 محجوز للتحكم في دخول ROM bootloader.
- NRST على CN6 pin 14 يتحكم به ESP32-S3 عبر ترانزستور open-drain.
- PB8 لا يستخدم كـI2C1_SCL في هذه النسخة؛ لا نشارك وظيفة Boot0 مع ناقل حساس.
- USART3 PB10/PB11 هو رابط التطبيق وجسر ROM bootloader.
- إذا استخدمنا jump-to-system-memory من التطبيق، تبقى دائرة PB8/NRST كمسار recovery احتياطي لتحديث أولي أو استرداد فشل.



## 9. تصحيح إلزامي لخريطة الموصلات بعد مراجعة UM2505 Rev.7

المراجعة الدقيقة لجدول موصلات NUCLEO-G474RE كشفت أخطاء ترقيم في النسخة السابقة. هذه هي الأرقام الصحيحة المعتمدة الآن:

| الإشارة | الموصل الصحيح |
|---|---|
| PA8 / HRTIM1_CHA1 / D7 | CN9 pin 8 |
| PA9 / HRTIM1_CHA2 / D8 | CN5 pin 1 |
| PA12 / HRTIM1_FLT1 (إن اختير) | CN10 pin 11 |
| PB10 / USART3_TX | CN9 pin 7 (D6) |
| PB11 / USART3_RX | CN10 pin 17 |
| PB8 / BOOT0 | CN7 pin 7، وله أيضاً موضع D15 على CN5 pin 10 |
| NRST | CN6 pin 14 |
| PB13 / SPI2_SCK | CN10 pin 29 |
| PB15 / SPI2_MOSI | CN10 pin 25 |
| PB6 / CS | CN5 pin 3 |
| PA4 / DAC1_OUT1 | CN8 A2 pin 3 |
| PA0 / ADC1 | CN8 A0 pin 1 |
| PA1 / ADC2 | CN8 A1 pin 2 |
| PB1 / COMP1 input | CN10 pin 23 |

**تصحيح وظيفة BOOT0:** دليل UM2505 Rev.7 يوضح أن BOOT0 غير موصول بوضع افتراضي إلى دائرة اختيار boot، وتُدار الوظيفة افتراضياً عبر option bytes. لا يكفي توصيل سلك إلى PB8 والقول إن ROM bootloader سيعمل. يجب أولاً ضبط option bytes بحيث يستخدم boot من PB8، والتحقق من jumper JP7 ومسار اللوحة. إذا تعذر ذلك، نستخدم jump-to-system-memory من التطبيق كمسار تحديث أساسي، مع ST-LINK recovery عند الفشل.

المصدر الرسمي: https://www.st.com/resource/en/user_manual/dm00556337-stm32g4-nucleo64-boards-mb1367-stmicroelectronics.pdf (UM2505 Rev.7، الصفحات 33–35).


## 10. تخصيص DAC1 لقناة تحكم VGA

بعد إضافة AD8336:
- PA4 / DAC1_OUT1 / Arduino A2 / CN8 pin3 = DAC control 1.
- PA5 / DAC1_OUT2 / Arduino D13 / CN5 pin6 = DAC control 2.
- يذهب الخرجان عبر resistor attenuators وRC إلى GPOS/GNEG ضمن0–0.6V وفق common-mode في داتا شيت AD8336.
- PA7 يبقى COMP2 envelope recovery.
- SPI2 PB13/PB15 وCS PB6 يبقى للمقاومة الرقمية MCP41100 الخاصة بـRvar.
- لذلك لا نستخدم SPI1 على PA5/PA6/PA7.

يجب التحقق من alternate function الخاص بـDAC1_OUT2 على نسخة STM32G474RE LQFP64 قبل PCB النهائي.


## 11. قنوات ADC إضافية للفحص الذاتي ومراقبة القدرة

بعد مراجعة Table 12 من STM32G474 datasheet وTable 15/موصلات Morpho في UM2505، يمكن تخصيص قنوات مراقبة لا تتعارض مع PA0/PA1 أو DAC/COMP/SPI:

| الوظيفة | رجل MCU | قناة ADC | موصل Nucleo | ملاحظة |
|---|---|---|---|---|
| تيار TX من shunt amplifier | PB1 | ADC1_IN12 | CN10 pin 23 | نفس الرجل COMP1_INP؛ حماية عتادية |
| جهد Drain/VDS عبر divider | PB0 | ADC1_IN15 | CN6 pin 34 أو CN8 A3 | لا اتصال مباشر بالـDrain |
| جهد البطارية | PC0 | ADC12_IN6 | CN7 pin 38 / CN8 A5 | SB36 يختار PC0 افتراضياً |
| +12V_AFE | PC1 | ADC12_IN7 | CN7 pin 36 / CN8 A4 | SB35 يختار PC1 افتراضياً؛ PB9 غير مستخدم |
| −12V_AFE بعد level-shift | PC2 | ADC12_IN8 | CN7 pin 35 | يجب تحويله إلى 0–3.3V |
| حرارة MOSFET/لوحة القدرة | PC3 | ADC12_IN9 | CN7 pin 37 | NTC divider |
| حرارة رأس البحث | PC4 | ADC2_IN5 | CN9 pin 2 / CN10 pin 33 | NTC داخل الرأس إذا أمكن |

### شروط التوصيل
- جميع قنوات المراقبة تمر عبر مقسمات/مضخمات مناسبة ومقاومات حماية؛ لا يوصل VDS أو rail سالب مباشرة إلى ADC.
- PB1 يستخدم لمقارنة COMP1 وللقراءة الرقمية من ADC1_IN12؛ يجب ألا يحمّل مسار الشنت أو يبطئ استجابة comparator.
- PC0/PC1 مرتبطان بجسور SB36/SB35 على لوحة Nucleo؛ تبقى إعدادات المصنع الافتراضية PC0 وPC1، ويجب التحقق منها قبل الاستخدام.
- هذه القنوات مخصصة للمراقبة البطيئة/الحرارية والقدرة؛ لا تزاحم زوج ADC1/ADC2 السريع PA0/PA1 الخاص بإشارة PI.
- PC4 يشارك موضع CN9 pin2 مع اختيار PA2/PC4؛ نستخدم PC4 كما في جدول الموصلات، ونتجنب USART1 على هذا الطرف.

المراجع:
- STM32G474 datasheet DS12288 Table 12: https://www.st.com/resource/en/datasheet/stm32g474re.pdf
- UM2505 Rev.7 Tables 14–17: https://www.st.com/resource/en/user_manual/dm00556337-stm32g4-nucleo64-boards-mb1367-stmicroelectronics.pdf


## 12. إخراج HRTIM إلى مفتاحي TMUX6219

بعد اعتماد TMUX6219 ثنائي التغذية، تثبت أرجل التحكم:
| الوظيفة | رجل MCU | خرج HRTIM | موصل Nucleo |
|---|---|---|---|
| TX MOSFET gate-driver input | PA8 | HRTIM1_CHA1 | CN9 pin 8 / D7 |
| SWb enable | PA9 | HRTIM1_CHA2 | CN5 pin 1 / D8 |
| High-gain AFE enable/blanking | PA10 | HRTIM1_CHB1 | CN9 pin 3 / D2 |

- PA8 وPA9 وPA10 كلها HRTIM outputs مؤكدة في STM32G474 datasheet Table12.
- PA10/HRTIM1_CHB1 متاح على CN9 pin3، وليس مستخدماً في USART3.
- HRTIM master يزامن Timer A وTimer B؛ PA9 يحدد SWb event عند TX-off، وPA10 يبقي high-gain مفصولاً حتى COMP2 recovery event.
- منطق TMUX6219 يقبل 1.8V، لذا 3.3V HRTIM logic مناسب.
- تغذية مفاتيح TMUX6219 هي ±12V_AFE، ومساراتها التناظرية يجب أن تبقى ضمن rails. لا يمرر أي switch transient يتجاوز±12V دون clamp محسوب.

المراجع:
- STM32G474 datasheet Table12: https://www.st.com/resource/en/datasheet/stm32g474re.pdf
- UM2505 Rev.7 Table15: https://www.st.com/resource/en/user_manual/dm00556337-stm32g4-nucleo64-boards-mb1367-stmicroelectronics.pdf
