# عقد بيانات التجارب في ISLAM LAB

كل تجربة تحفظ بصيغة قابلة لإعادة التشغيل، ولا يسمح بحذف مصدر البيانات أو وحداتها.

## الحقول الأساسية

- `schema_version`: إصدار مخطط البيانات.
- `experiment_id`: معرف فريد للتجربة.
- `created_utc`: وقت الإنشاء UTC.
- `source_type`: `synthetic` / `simulated` / `user_provided` / `measured` / `validated`. لا تستخدم `measured` إلا لبيانات التقطها جهاز قياس فعلي موثق.
- `model_name` و`model_version`: اسم وإصدار المحرك عند وجود محاكاة.
- `hardware`: جهاز القياس، القناة، مجال الدخل، ومعدل العينة عند القياس.
- `acquisition_origin`: طريقة وصول البيانات مثل `generated_by_lab_model` أو `user_entry_or_file_import` أو `device_capture`.
- `measurement_status`: حالة الإثبات، مثل `not_a_hardware_measurement` أو `not_verified_as_device_measurement` أو `device_capture_verified`.
- `measurement_device`: تعريف جهاز الالتقاط عند القياس الحقيقي؛ لا يملأ ببيانات افتراضية.
- `created_epoch_ms` أو `created_utc`: وقت إنشاء التجربة.
- `conditions`: شروط البيئة والمواد والهندسة.
- `signals`: قنوات زمنية، وكل قناة لها وحدة ومعدل عينات وطوابع زمنية أو محور زمن واضح.
- `calibration`: معلومات المعايرة وعدم اليقين.
- `notes`: ملاحظات المستخدم.

## مثال وصفي

```json
{
  "schema_version": "1.0",
  "experiment_id": "lab-example-001",
  "source_type": "synthetic",
  "model_name": "exponential-decay-fixture",
  "model_version": "0.1.0",
  "conditions": {
    "amplitude_mV": 1000.0,
    "tau_us": 24.0,
    "noise_rms_mV": 2.0
  },
  "signals": [{
    "channel": "RX_TEST",
    "unit": "mV",
    "sample_times_us": [8, 12, 16, 24, 36, 52, 72, 100],
    "values": [716.53, 606.53, 513.42, 367.88, 223.13, 114.61, 49.79, 15.50]
  }],
  "calibration": {
    "status": "not_applicable",
    "uncertainty": "not_characterized"
  }
}
```

المثال تعليمي، والقيم توضيحية. بيانات المستخدم التي أُدخلت يدوياً أو استوردت من ملف تُوسم `user_provided` ولا تتحول تلقائياً إلى `measured`. القياس الحقيقي يجب أن يتضمن تعريف الجهاز والقناة والمعايرة وحالة التشبع ومعدل أخذ العينات، مع حفظ البيانات الخام.
