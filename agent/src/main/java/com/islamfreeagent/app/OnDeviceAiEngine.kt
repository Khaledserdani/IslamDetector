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
            val candidate = Engine(
                EngineConfig(
                    modelPath = modelPath,
                    backend = Backend.CPU(),
                    cacheDir = cacheDirectory
                )
            )
            try {
                candidate.initialize()
            } catch (error: Exception) {
                // LiteRT-LM requires that an Engine whose initialize() failed is not closed.
                callback.onFailure(error.message ?: "فشل تحميل النموذج")
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
                val reply = conversation!!.sendMessage(prompt).text
                callback.onSuccess(reply)
            } catch (error: Exception) {
                callback.onFailure(error.message ?: "تعذر توليد الرد محلياً")
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
