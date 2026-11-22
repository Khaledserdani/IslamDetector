package com.islamfreeagent.app;

import java.util.Arrays;
import java.util.List;

/** User-facing capability map; status is explicit and never enables planned engines. */
final class AgentLabCatalog {
    static final class Entry {
        final String title;
        final String status;
        final String detail;
        Entry(String title, String status, String detail) {
            this.title = title; this.status = status; this.detail = detail;
        }
    }

    private static final List<Entry> ENTRIES = Arrays.asList(
            new Entry("دوائر DC المقاومة", "متاح داخل التطبيق",
                    "مقاومات مثالية ومصدر جهد واحد؛ تحليل عقدي وفحص KCL، مع تشغيل بموافقة المستخدم."),
            new Entry("RLC المتسلسل AC والعابر", "مرجع Python فقط",
                    "يوجد نموذج مرجعي في المستودع؛ لم يُنقل بعد إلى محرك Android."),
            new Entry("شبكات AC متعددة العقد", "مرجع Python فقط",
                    "محلل RLC خطي باستخدام MNA؛ غير متاح للتنفيذ داخل APK حالياً."),
            new Entry("SPICE عام وأشباه الموصلات والتبديل", "مخطط",
                    "لا يوجد محرك تنفيذي معتمد داخل التطبيق حالياً."),
            new Entry("الأنظمة المضمنة ومعالجة الإشارات", "مخطط",
                    "تحتاج محركات واختبارات مرجعية مستقلة قبل تفعيلها."),
            new Entry("الحرارة والموائع والميكانيكا والمواد", "مخطط",
                    "مجالات مستقبلية؛ لا تُعرض نتائج محاكاة قبل تنفيذ المحركات والتحقق منها."),
            new Entry("الإحصاء والتحقق العلمي", "مخطط",
                    "سجل الأدلة والتحقق المستقل وتقدير عدم اليقين ضمن مراحل التطوير.")
    );

    private AgentLabCatalog() {}

    static String describe() {
        StringBuilder text = new StringBuilder("خريطة قدرات ISLAM LAB\n\n");
        for (Entry entry : ENTRIES) {
            text.append(entry.title).append("\nالحالة: ").append(entry.status)
                    .append("\n").append(entry.detail).append("\n\n");
        }
        text.append("لا يستطيع الوكيل تشغيل أي مختبر إلا إذا كان محرك Android الخاص به منفذاً ومسموحاً.");
        return text.toString();
    }
}
