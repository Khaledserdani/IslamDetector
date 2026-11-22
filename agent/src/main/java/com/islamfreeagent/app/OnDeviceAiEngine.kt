package com.islamfreeagent.app

import com.google.ai.edge.litertlm.Backend
import com.google.ai.edge.litertlm.Contents
import com.google.ai.edge.litertlm.Conversation
import com.google.ai.edge.litertlm.ConversationConfig
import com.google.ai.edge.litertlm.Engine
import com.google.ai.edge.litertlm.EngineConfig
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors

/**
 * Owns LiteRT-LM on one worker thread. No network inference, cloud API, or computer bridge.
 * The model file is downloaded by the user-facing Android DownloadManager flow.
 */
internal class OnDeviceAiEngine(
    private val cacheDirectory: String
) {
    interface Callback {
        fun onSuccess(message: String)
        fun onFailure(message: String)
    }

    private val systemInstruction = "أنت إسلام، مساعد عربي يعمل محلياً دون إنترنت. " +
        "أجب بالعربية الواضحة والدارجة الجزائرية عند الحاجة. " +
        "كن دقيقاً، لا تخترع نتائج اختبارات أو قدرات غير موجودة. " +
        "في المسائل الهندسية افصل بين الحساب النظري والقياس الفعلي، " +
        "واطلب التحقق قبل أي إجراء يؤثر في الملفات أو الأجهزة."

    private val executor: ExecutorService = Executors.newSingleThreadExecutor()
    private var engine: Engine? = null
    private var conversation: Conversation? = null
    private var loadedPath: String? = null
    @Volatile private var closed = false

    fun load(modelPath: String, callback: Callback) {
        executor.execute {
            if (closed) {
                callback.onFailure("محرك الذكاء الاصطناعي متوقف")
                return@execute
            }
            if (loadedPath == modelPath && conversation != null) {
                callback.onSuccess("النموذج جاهز")
                return@execute
            }
            closeModel()
            // Keep construction and initialization inside the guarded block: native/runtime
            // setup can fail before initialize() is reached, and the UI must receive a result.
            val candidate = try {
                Engine(
                    EngineConfig(
                        modelPath = modelPath,
                        backend = Backend.CPU(),
                        cacheDir = cacheDirectory
                    )
                ).also { it.initialize() }
            } catch (error: Exception) {
                // LiteRT-LM requires that an Engine whose initialize() failed is not closed.
                callback.onFailure(error.message ?: "فشل تحميل النموذج")
                return@execute
            } catch (error: LinkageError) {
                callback.onFailure(error.message ?: "مكتبات تشغيل الذكاء المحلي غير متاحة على هذا الهاتف")
                return@execute
            }
            engine = candidate
            try {
                conversation = candidate.createConversation(
                    ConversationConfig(
                        systemInstruction = Contents.of(systemInstruction),
                        thinkingConfig = com.google.ai.edge.litertlm.ThinkingConfig(
                            enableThinking = false,
                            thinkingTokenBudget = 0
                        ),
                        maxOutputToken = 512
                    )
                )
                loadedPath = modelPath
                callback.onSuccess("النموذج المحلي جاهز على الهاتف")
            } catch (error: Exception) {
                closeModel()
                callback.onFailure(error.message ?: "تعذر إنشاء المحادثة المحلية")
            }
        }
    }

    fun sendMessage(prompt: String, callback: Callback) {
        executor.execute {
            if (closed || conversation == null) {
                callback.onFailure("حمّل النموذج المحلي أولاً")
                return@execute
            }
            try {
                val reply = conversation!!.sendMessage(prompt).toString()
                callback.onSuccess(reply)
            } catch (error: Exception) {
                callback.onFailure(error.message ?: "تعذر توليد الرد محلياً")
            }
        }
    }

    fun planTask(taskDescription: String, callback: Callback) {
        executor.execute {
            val activeEngine = engine
            if (closed || activeEngine == null || conversation == null) {
                callback.onFailure("حمّل النموذج المحلي أولاً")
                return@execute
            }
            var planner: Conversation? = null
            try {
                val instruction = "أنت مخطط أدوات آمن داخل تطبيق إسلام. لا تنفذ أي شيء بنفسك. " +
                    "إذا كانت المهمة تطلب إنشاء ملف أو ملفات نصية وكتابة محتواها ثم قراءتها، أعد كائن JSON فقط " +
                    "إذا طلبت ملفاً واحداً فأعد JSON بالمفاتيح action وfilename وcontent واجعل action write_and_read_text_file. " +
                    "إذا طلبت عدة ملفات فأعد JSON بالمفاتيح action وfiles واجعل action write_and_read_text_files، " +
                    "وfiles مصفوفة تضم عنصراً لكل ملف مطلوب، وكل عنصر يحوي filename وcontent. لا تسقط أي ملف. " +
                    "استخدم أسماء TXT بسيطة دون مسارات، وانقل المحتوى العربي المطلوب حرفياً دون ترجمته. " +
                    "إذا طلب المستخدم تحليل أو محاكاة دارة DC بمقاومات ومصدر جهد مثالي، أعد JSON فقط بالمفاتيح action وlab_id وground وsource_node وsource_voltage_v وresistors. " +
                    "اجعل action يساوي simulate_lab وlab_id يساوي dc_resistive_network. " +
                    "resistors مصفوفة عناصرها كائنات بالمفاتيح a وb وohms، وكل عنصر يمثل مقاومة واحدة بالأوم. " +
                    "لا تخترع قيماً ناقصة؛ إذا لم يذكر المستخدم التوصيلات أو الجهد الكافي فاجعل action unsupported. " +
                    "هذا المختبر يحل مقاومات خطية ومصدراً مثالياً واحداً فقط، ولا يمثل المكثفات أو الملفات أو التبديل أو الحرارة أو العتاد الحقيقي. " +
                    "إذا لم تكن المهمة من هذا النوع أو كانت تحتاج مختبراً غير منفذ فأعد JSON فقط بالمفتاح action وقيمته unsupported. " +
                    "لا تضف Markdown أو شرحاً خارج JSON، ولا تقترح أوامر نظام أو شبكة أو حذف ملفات.";
                val taskConversation = activeEngine.createConversation(
                    ConversationConfig(
                        systemInstruction = Contents.of(instruction),
                        thinkingConfig = com.google.ai.edge.litertlm.ThinkingConfig(
                            enableThinking = false,
                            thinkingTokenBudget = 0
                        ),
                        maxOutputToken = 2048
                    )
                )
                planner = taskConversation
                val reply = taskConversation.sendMessage(taskDescription).toString()
                callback.onSuccess(reply)
            } catch (error: Exception) {
                callback.onFailure(error.message ?: "تعذر تحليل المهمة محلياً")
            } finally {
                planner?.close()
            }
        }
    }

    fun resetConversation(callback: Callback) {
        executor.execute {
            val activeEngine = engine
            if (closed || activeEngine == null) {
                callback.onFailure("النموذج غير محمّل")
                return@execute
            }
            try {
                conversation?.close()
                conversation = activeEngine.createConversation(
                    ConversationConfig(
                        systemInstruction = Contents.of(systemInstruction),
                        thinkingConfig = com.google.ai.edge.litertlm.ThinkingConfig(
                            enableThinking = false,
                            thinkingTokenBudget = 0
                        ),
                        maxOutputToken = 512
                    )
                )
                callback.onSuccess("بدأت محادثة جديدة")
            } catch (error: Exception) {
                callback.onFailure(error.message ?: "تعذر بدء محادثة جديدة")
            }
        }
    }

    fun close() {
        if (closed) return
        closed = true
        executor.execute {
            closeModel()
            executor.shutdown()
        }
    }

    private fun closeModel() {
        conversation?.close()
        conversation = null
        engine?.close()
        engine = null
        loadedPath = null
    }
}
