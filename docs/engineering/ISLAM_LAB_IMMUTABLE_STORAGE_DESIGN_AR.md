# تصميم طبقة التخزين العلمي غير القابلة للمحو — ISLAM LAB

**الإصدار:** 0.2  
**الحالة:** تصميم مع تنفيذ أولي للجداول وواجهات الالتقاط والمراجعة والتحليل والتقييم وسجل الموافقات؛ لم يثبت البناء بعد  
**المسار:** `docs/engineering/ISLAM_LAB_IMMUTABLE_STORAGE_DESIGN_AR.md`  
**النطاق:** فرع `feature/islam-lab-foundation` فقط

## 1. القرار المعماري

لا نعيد توظيف جدول `experiments` الحالي بوصفه مخزن الالتقاطات الخام. فهو جدول قديم يسمح بإعادة الحفظ والاستبدال وإعادة التسمية والحذف، كما تعتمد عليه واجهات واختبارات قائمة.

بدلاً من ذلك، تضاف طبقة مستقلة إلى قاعدة البيانات نفسها. تبقى سجلات `experiments` وCSV القديمة قابلة للقراءة والترحيل، ولا تتحول تلقائياً إلى قياسات جهاز أو إلى سجلات مؤكدة.

الطبقة الجديدة تفصل بين:
1. الالتقاط الخام الثابت.
2. أحداث المراجعة والتصحيح المتتابعة.
3. تشغيلات التحليل ومخرجاتها.
4. تقييم مجموعات البيانات والمرشحين.
5. أحداث نشر الخوارزميات والرجوع عنها.

**لا تغيير في Firmware أو بروتوكول V2 أو مسار الكشف ضمن هذه المرحلة.**

## 2. ترقية قاعدة البيانات

- الإصدار السابق في التطبيق هو DB_VERSION=2؛ نُفذت ترقية إضافية إلى DB_VERSION=4. الترقية 2→3 تضيف جداول الالتقاط والتقييم، والترقية 3→4 تضيف سجل قرارات الاعتماد.
- Migration 2→3 تضيف الجداول والفهارس والقيود فقط.
- لا تحذف أو تعيد إنشاء جدول `experiments`، ولا تعيد كتابة CSV القديم، ولا تعيد تصنيف مصدره.
- لا تنشئ صفوف `captures` تلقائياً من التجارب القديمة؛ تحويل سجل قديم يحتاج عملية استيراد صريحة تحفظ الأصل ومصدر التحويل.
- يجب أن يكون الترحيل داخل معاملة SQLite التي يديرها `SQLiteOpenHelper`. إذا فشل إنشاء أي جدول، يجب أن تتراجع المعاملة ولا تترك قاعدة نصف محدثة.
- يضاف اختبار يفتح قاعدة v2 فعلية فيها أكثر من سجل، يرقّيها، ثم يثبت تطابق معرفات CSV والبيانات الوصفية وعدد الصفوف قبل وبعد.

## 3. الجداول المقترحة

### 3.1 captures — الالتقاطات الخام

الحقول:

| الحقل | النوع | القاعدة |
|---|---|---|
| capture_id | TEXT | UUID/معرف فريد، PRIMARY KEY |
| session_id | TEXT | معرف جلسة غير فارغ |
| sequence | INTEGER | غير سالب |
| source_type | TEXT | synthetic / user_provided / instrument / islam_detector |
| captured_at_utc | TEXT NULL | وقت مدني اختياري |
| monotonic_start_tick | INTEGER NULL | ساعة الجهاز الرتيبة إن توفرت |
| tick_frequency_hz | INTEGER NULL | موجب عند وجود ticks |
| device_id | TEXT NULL | لا يخترع للمصادر غير الجهاز |
| stm32_firmware | TEXT NULL | اختياري |
| esp32_firmware | TEXT NULL | اختياري |
| coil_profile_id | TEXT NULL | معرف الملف/المجس كما ورد |
| acquisition_config_id | TEXT NULL | معرف إعداد الالتقاط |
| payload_format | TEXT | ترميز ثنائي معروف ومعلن |
| payload_blob | BLOB | البايتات الأصلية كما استلمت |
| payload_length_bytes | INTEGER | يساوي طول BLOB |
| payload_crc32 | TEXT | كشف تلف النقل |
| payload_sha256 | TEXT | 64 خانة hex؛ لا يوجد fallback |
| sample_count | INTEGER | موجب عند اكتمال الالتقاط |
| transport_status | TEXT | complete / incomplete / corrupted |
| created_epoch_ms | INTEGER | وقت الحفظ المحلي |

قيود الهوية:
- PRIMARY KEY على `capture_id`.
- UNIQUE على (`session_id`, `sequence`) لمنع تكرار رقم التسلسل داخل الجلسة.
- لا يستخدم SHA-256 كهوية للسجل؛ هو بصمة سلامة للمحتوى فقط.
- يجوز لالتقاطين مختلفين أن يحتويَا بايتات متطابقة وأن يبقيا سجلين مستقلين إذا اختلفت هويتهما.
- لا يعتبر الالتقاط صالحاً للتحليل الميداني إلا إذا كان `transport_status=complete` وتطابقت الأطوال وCRC وSHA-256.
- لا تُحفظ حمولة مبتورة على أنها مكتملة. يمكن الاحتفاظ بها كـincomplete للتشخيص، لكنها لا تدخل التدريب أو التقييم.

**سياسة الكتابة:** واجهة التخزين لا تعرض update أو delete للالتقاط. إدراج الالتقاط يتم مرة واحدة، وبعد حساب SHA-256 والتحقق من الطول وCRC. فشل حساب SHA-256 يوقف الحفظ ويرجع خطأ واضحاً؛ لا يسمح بـhashCode أو بصمة بديلة.

### 3.2 review_events — تاريخ المراجعة append-only

كل تصحيح هو حدث جديد، ولا يعدّل حدثاً سابقاً.

الحقول:
- `event_id` TEXT PRIMARY KEY.
- `capture_id` TEXT NOT NULL REFERENCES captures(capture_id).
- `event_time_epoch_ms` INTEGER NOT NULL.
- `reviewer_id` TEXT NOT NULL.
- `previous_lifecycle_status` و`new_lifecycle_status`.
- `previous_ground_truth_status` و`new_ground_truth_status`.
- `reason_code` TEXT NOT NULL.
- `review_note` TEXT NULL.
- `evidence_type` و`evidence_ref` اختياريان.
- `previous_event_id` TEXT NULL لربط تسلسل أحداث المراجعة.

حالات دورة المراجعة مستقلة عن الحقيقة الأرضية:
- lifecycle: CAPTURED, NEEDS_REVIEW, REVIEWED, ELIGIBLE_FOR_TRAINING, REJECTED, INCONCLUSIVE.
- ground truth: UNKNOWN, CONFIRMED, REJECTED, INCONCLUSIVE.

لا توجد حالة lifecycle باسم GROUND_TRUTH_CONFIRMED؛ تأكيد الحقيقة الأرضية محور مستقل. لا يؤدي ضغط المستخدم وحده إلى CONFIRMED. يجب أن يحمل الحدث سبباً ودليلاً/مرجع تحقق مناسباً. البيانات synthetic لا يجوز أن تتحول إلى حقيقة أرضية مؤكدة.

تستخرج الحالة الحالية من آخر حدث صالح لكل محور. يمكن إضافة cache لاحقاً للأداء، لكن سجل الأحداث يبقى المصدر المرجعي، وأي cache قابل لإعادة البناء.

### 3.3 analysis_runs — نتائج التحليل

كل تشغيل تحليل صف مستقل:
- `analysis_run_id` PRIMARY KEY.
- `capture_id` REFERENCES captures.
- `input_payload_sha256` نسخة من بصمة الالتقاط وقت التحليل.
- `algorithm_id`, `algorithm_version` إلزاميان.
- `model_sha256` اختياري عند وجود نموذج.
- `parameters_json` و`result_json` محفوظان كما شغّلا، مع التحقق من JSON.
- `started_epoch_ms`, `completed_epoch_ms`.
- `run_status`: complete / failed / cancelled.

لا يكتب التحليل فوق الالتقاط أو نتيجة تحليل سابقة. اختلاف الخوارزمية أو المعلمات ينتج صفاً جديداً.

### 3.4 evaluation_runs وevaluation_items — تقييم المرشحين

`evaluation_runs`:
- معرف تشغيل التقييم.
- `dataset_manifest_json` وبصمة SHA-256 له.
- معرفات وإصدارات champion وcandidate.
- `metrics_json`، `decision`، `created_epoch_ms`.
- مرجع مجموعة الاختبار المستقلة وحدود قبولها.

`evaluation_items`:
- التقييم، الالتقاط، split (train/validation/test/shadow).
- `group_key` لتجميع الالتقاطات المرتبطة بالتجربة/الهدف/جلسة الاختبار ومنع تسربها بين التقسيمات.
- النتيجة المتوقعة والنتيجة المحسوبة عند توفرهما.

لا يجوز أن يظهر الالتقاط أو المجموعة المرتبطة به في أكثر من split داخل التقييم نفسه. تحفظ manifest وبصمتها لإعادة إنتاج القرار.

### 3.5 evaluation_decisions — قرار الاعتماد البشري

فصلنا نتيجة التقييم الحسابية عن قرار الترقية. لا يقبل سجل التقييم قيمة PROMOTE مباشرة؛ أنواع التقييم هي FIELD_CANDIDATE أو SIMULATION_ONLY أو SHADOW_ONLY. قرار PROMOTE/REJECT/SHADOW_ONLY يسجل لاحقاً كحدث append-only يتضمن:
- decision_id وevaluation_run_id.
- policy_id وpolicy_version.
- reviewer_id وrationale وevidence_ref.
- decided_epoch_ms.

لا يمكن إنشاء قرار PROMOTE إلا لتقييم FIELD_CANDIDATE يحتوي مجموعة test، ويجب أن تكون كل التقاطاته من مصدر ميداني غير اصطناعي، وآخر حالة مراجعة لها ELIGIBLE_FOR_TRAINING مع ground truth CONFIRMED. التفعيل يتحقق من وجود آخر قرار PROMOTE لنفس التقييم، وأن الخوارزمية والإصدار المطلوبين يطابقان المرشح الذي جرى تقييمه.

هذا لا يجعل القرار تلقائياً أو يثبت صحة المقاييس؛ إنه يفصل الحساب عن الاعتماد البشري ويترك أثراً قابلاً للتدقيق.

### 3.6 deployment_events — سجل تفعيل الخوارزمية

كل تفعيل أو رجوع حدث مستقل:
- `deployment_event_id` PRIMARY KEY.
- `previous_algorithm_id/version`.
- `new_algorithm_id/version`.
- `model_sha256` عند وجود نموذج.
- `action`: activate / rollback / reject.
- `reason`, `actor_id`, `event_time_epoch_ms`.
- `evaluation_run_id` مرجع التقييم الذي أجاز التغيير.

هذا الجدول سجل تدقيق، وليس آلية تشغيل firmware أو تبديل مباشر على العتاد.

## 4. الحماية وحدودها

- تنشئ Triggers على `captures` تمنع UPDATE وDELETE، وعلى جداول الأحداث تمنع UPDATE وDELETE.
- لا نعتمد على Trigger وحده: واجهة Repository لا توفر دوال تعديل/حذف، ولا تمرر كائن SQLite إلى واجهة المستخدم.
- تكتب كل عملية متعددة الصفوف بمعاملة ذرية.
- لا يستخدم `ON CONFLICT REPLACE` لأي معرفات في الطبقة الجديدة. عند التعارض تفشل العملية وتبلغ المستدعي.
- مفاتيح SQLite الأجنبية تكون مفعلة عبر `PRAGMA foreign_keys=ON` في كل اتصال مناسب.
- هذه حماية من أخطاء التطبيق والكتابة العرضية، وليست حماية جنائية ضد شخص يملك ملف قاعدة البيانات أو يستطيع تعديل التطبيق/SQLite مباشرة. يمكن العبث المحلي المتعمد؛ لذلك تصدير نسخة موثقة وموقعة مستقبلاً قد يكون ضرورياً.

## 5. واجهة التخزين المقترحة

تكون الواجهة الجديدة منفصلة عن واجهة `ExperimentStore` القديمة، مثلاً `ScientificCaptureStore`، وتوفر عمليات محدودة:
- `insertCapture(...)`: إدراج وحيد مع التحقق والبصمات.
- `getCapture(captureId)` وعمليات القراءة/البحث.
- `appendReviewEvent(...)`: إضافة حدث مراجعة مع التحقق من الحالة السابقة.
- `appendAnalysisRun(...)`.
- `appendEvaluationRun(...)` و`appendEvaluationItem(...)`.
- `appendDeploymentEvent(...)`.

لا توجد دوال `updateCapture`, `deleteCapture`, `replaceCapture` أو `overwriteReview`.

تُنفذ كتابة الالتقاط على خيط خلفي، ولا تنتظرها حلقة أخذ العينات في STM32. في V2 يرسل الجهاز الحزمة إلى Android/المخزن بعد اكتمال الالتقاط؛ تفاصيل النقل خارج هذا التصميم.

## 6. اختبارات القبول قبل ربط الواجهة

1. حفظ التقاط وإغلاق DB ثم إعادة فتحها: تطابق كل بايت وبصمة.
2. إدراج capture_id نفسه مرتين: يفشل الإدراج الثاني ولا يستبدل الأول.
3. إدراج JSON/حمولة متطابقة بمعرفي capture_id مختلفين وتسلسلين مختلفين: يحتفظ بالسجلين.
4. تكرار (session_id, sequence) مع capture_id مختلف: يرفض بسبب تعارض التسلسل.
5. فشل SHA-256 أو CRC أو طول الحمولة: لا ينشأ سجل مكتمل.
6. لا يمكن تعديل/حذف capture عبر Repository، وتمنع Triggers محاولات SQL المباشرة العادية.
7. تصحيح المراجعة مرتين: يحتفظ بالحدثين وبالحالتين السابقة والجديدة، وتظهر الحالة الأحدث عند القراءة.
8. حدث مراجعة لا يغير BLOB أو SHA-256 للخام.
9. رفض تحويل synthetic إلى ground truth CONFIRMED.
10. حفظ تحليلين مختلفين لنفس الالتقاط: يحتفظ بهما مع ربطهما ببصمة الخام.
11. رفض split متعارض للالتقاط أو group_key داخل evaluation واحدة.
12. ترقية قاعدة v2 إلى v3 تحفظ كل سجلات experiments القديمة وCSV والبيانات الوصفية دون تغيير.
13. فشل Migration في منتصفه: rollback كامل وعدم إعلان DB_VERSION=3.
14. اختبار أن التخزين والتحليل لا يحجبان واجهة المستخدم أو مسار أخذ العينات.

## 7. نقاط لم تُحسم بعد

لا يمكن تثبيت هذه القيم من الملفات الحالية، ولا ينبغي اختلاقها:
- صيغة `payload_format` النهائية وترتيب القنوات والنوافذ.
- الحد الأعلى الواقعي لحجم BLOB وسياسة تقسيم الالتقاط الكبير.
- هل تحفظ أزمنة العينات داخل الحمولة الثنائية أم في جدول/كتلة منفصلة.
- سياسة هوية `group_key` في التقييم عندما لا تتوفر هوية هدف أو تجربة ميدانية موثقة.
- آلية توقيع/تصدير سجل التدقيق إذا تطلب الأمر مقاومة العبث خارج التطبيق.

تبقى هذه النقاط مفتوحة إلى أن يعتمد عقد بيانات V2 وملف acquisition profile. لا تمنع تنفيذ الهيكل والجداول والاختبارات المستقلة عن صيغة الحمولة النهائية.

## 8. حالة التنفيذ والحدود

أضيفت مبدئياً الملفات التالية إلى فرع المختبر:
- `ScientificStorageSchema.java`: جداول captures وreview_events وanalysis_runs وevaluation_runs وevaluation_items وevaluation_decisions وdeployment_events مع Triggers append-only.
- `ScientificCaptureStore.java`: إدراج الالتقاط والتحقق من SHA-256/CRC32 عند القراءة، وإضافة أحداث المراجعة، وربط التحليل ببصمة الخام، وحفظ التقييم ومجموعات split، وتسجيل قرار اعتماد مستقل، ومنع تفعيل نسخة دون قرار PROMOTE مطابق.
- `ExperimentStore.java`: ترقية DB_VERSION إلى 4 مع ترحيل إضافي.
- `ScientificCaptureStoreTest.java`: اختبارات Robolectric تشمل حفظ الالتقاطات المتطابقة بهويات مستقلة، ومنع الاستبدال، وسجل التصحيح، وترحيل قاعدة قديمة، ومطابقة بصمة التحليل، ومنع تسرب group_key، واشتراط الاعتماد قبل التفعيل.

هذه مرحلة تنفيذ أولي وليست اعتماداً نهائياً. لم يثبت نجاح Gradle أو الاختبارات بعد. أضيف workflow مخصصاً لتشغيل `:lab:testDebugUnitTest` باستخدام Gradle 8.9 وJava 17، لكن يجب فحص نتيجة تشغيله الفعلية قبل إعلان النجاح.

لم يُربط التخزين بواجهة المختبر أو الجهاز، ولم ينفذ تدريب نموذج أو تبديل خوارزمية حقيقي. لا يغيّر هذا العمل عتاد الجهاز ولا يوقف الكشف ولا يدمج المختبر مع الجهاز.
