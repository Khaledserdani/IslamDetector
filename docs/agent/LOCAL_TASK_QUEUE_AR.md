# تشغيل طابور مهام وكيل إسلام محلياً

هذه الأداة مجانية ولا تحتاج Ollama أو API أو اتصالاً بالإنترنت. تحتاج Python 3.10 أو أحدث فقط.

## الأوامر

من جذر المستودع:

```bash
python tools/islam_agent/task_queue.py list
python tools/islam_agent/task_queue.py next
```

لبدء مهمة:

```bash
python tools/islam_agent/task_queue.py set agent-004 in_progress --note "بدأ التنفيذ"
```

عند إكمال شروط القبول والاختبارات:

```bash
python tools/islam_agent/task_queue.py set agent-004 completed --note "تم التحقق من شروط القبول"
```

إذا توقفت المهمة بسبب عائق:

```bash
python tools/islam_agent/task_queue.py set agent-004 blocked --note "سبب التعطّل"
```

ولإرجاع مهمة محظورة إلى قائمة الانتظار:

```bash
python tools/islam_agent/task_queue.py set agent-004 pending --note "زالت العقبة"
```

## قواعد السلامة

- الانتقالات المسموحة: pending إلى in_progress؛ in_progress إلى pending أو blocked أو completed؛ blocked إلى pending.
- لا يمكن إكمال مهمة مباشرة من pending أو إعادة فتح مهمة completed تلقائياً.
- تُكتب الذاكرة إلى ملف مؤقت ثم تستبدل ذرياً لتقليل احتمال تلف JSON عند انقطاع الكتابة.
- الأداة لا تنفذ أوامر shell ولا تتصل بـGitHub أو Ollama.
- التغييرات تبقى محلية حتى تقوم أنت بعمل commit وpush؛ لا يوجد رفع تلقائي.
- لا تضع أسراراً أو مفاتيح وصول في ملاحظات المهام.
- لا تسجل المهمة completed إلا بعد تحقق شروط القبول فعلياً.

## حدود النسخة الحالية

هذه أداة طابور محلية بسيطة، وليست بعد وكيلاً لغوياً مستقلاً. لا توفر قفلاً بين عمليتين متزامنتين؛ شغّل نسخة واحدة منها في كل مرة. التكامل مع نموذج محلي وصلاحيات GitHub المحدودة مرحلة لاحقة.