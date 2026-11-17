# ISLAM LAB — عقد أدوات MCP (مسودة)

الحالة: مواصفات أولية، لا يوجد خادم MCP منشور أو متصل بـChatGPT بعد.

## قواعد عامة
- جميع الطلبات مرتبطة بـ project_id.
- عمليات التعديل تتطلب expected_revision لمنع الكتابة فوق تحديث أحدث.
- كل تشغيل يعيد run_id، engine_version، netlist_hash، analysis_type، status، warnings.
- نتائج المحاكاة للقراءة فقط؛ لا تُعد قياسات عتادية.
- لا توجد أداة لتنفيذ shell أو JavaScript أو Python أو أوامر نظام اعتباطية.
- رفض أي netlist يحوي أوامر ملفات/نظام أو directives خارج القائمة المسموحة.
- حدود للوقت والذاكرة وعدد العقد والمكونات وحجم النتائج.
- المصادقة إلزامية، والمفاتيح لا تحفظ في الواجهة الأمامية.

## الأدوات
### lab_list_projects
يعيد المشاريع المتاحة للمستخدم.

### lab_create_project
المدخلات: name, description, template_id?
المخرجات: project_id, revision.

### lab_get_project
المدخلات: project_id
المخرجات: بيانات المشروع ومكوناته واتصالاته وآخر revision.

### lab_add_component
المدخلات: project_id, expected_revision, component_type, reference, pins, parameters, position
المخرجات: component_id, new_revision.

### lab_update_component
المدخلات: project_id, expected_revision, component_id, parameter_patch
المخرجات: new_revision.

### lab_connect_nodes
المدخلات: project_id, expected_revision, endpoint_a, endpoint_b
المخرجات: connection_id, new_revision.

### lab_validate_circuit
المدخلات: project_id, revision
المخرجات: errors, warnings, floating_nodes, missing_ground.

### lab_generate_netlist
المدخلات: project_id, revision
المخرجات: netlist_text, netlist_hash, engine_compatibility.

### lab_run_analysis
المدخلات: project_id, revision, analysis: op|tran|ac|dc, options
المخرجات: run_id, status, engine_version, warnings.

### lab_get_run
المدخلات: run_id
المخرجات: status, summary, convergence, measurements, artifacts.

### lab_get_waveform
المدخلات: run_id, trace_name, start?, end?, max_points?
المخرجات: units, samples, downsample_method.

### lab_compare_runs
المدخلات: run_id_a, run_id_b, trace_names
المخرجات: aligned comparison metrics and differences.

### lab_export_project
المدخلات: project_id, revision, format: islamlab|spice|csv|report
المخرجات: artifact_id, filename, media_type, checksum.

### lab_get_audit_log
المدخلات: project_id, cursor?, limit?
المخرجات: actor, action, timestamp, revision, summary.

## صلاحيات
- read: list/get/validate/results/export.
- write: create/update/connect.
- simulate: run_analysis.
- admin: manage users/keys.
تُفصل الصلاحيات ويُسجل كل استدعاء. يمكن طلب تأكيد منفصل قبل التعديلات أو تشغيل تحليل ثقيل.
