package com.islamfreeagent.app;

import org.json.JSONObject;
import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;

import java.io.File;

import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
public class AgentTaskToolRunnerTest {
    @Rule public TemporaryFolder temporary = new TemporaryFolder();

    @Test public void writesAndReadsBackOnlyInsideWorkspace() throws Exception {
        String content = "ISLAM FREE AGENT يعمل بنجاح.";
        JSONObject plan = new JSONObject()
                .put("action", "write_and_read_text_file")
                .put("filename", "test.txt")
                .put("content", content);
        JSONObject result = new AgentTaskToolRunner(temporary.getRoot()).execute(plan);
        assertTrue(result.getBoolean("verified"));
        assertEquals(content, result.getString("content"));
        assertTrue(new File(temporary.getRoot(), "test.txt").isFile());
    }

    @Test public void rejectsPathTraversal() throws Exception {
        JSONObject plan = new JSONObject()
                .put("action", "write_and_read_text_file")
                .put("filename", "../escape.txt")
                .put("content", "blocked");
        try {
            AgentTaskToolRunner.validate(plan);
            fail("path traversal must be rejected");
        } catch (IllegalArgumentException expected) {
            assertTrue(expected.getMessage().contains("اسم الملف"));
        }
    }

    @Test public void rejectsUnknownActionsAndExtraFields() throws Exception {
        JSONObject action = new JSONObject()
                .put("action", "run_shell")
                .put("filename", "test.txt")
                .put("content", "no");
        try {
            AgentTaskToolRunner.validate(action);
            fail("unknown action must be rejected");
        } catch (IllegalArgumentException expected) {
            // expected
        }

        JSONObject extra = new JSONObject()
                .put("action", "write_and_read_text_file")
                .put("filename", "test.txt")
                .put("content", "no")
                .put("command", "rm -rf /");
        try {
            AgentTaskToolRunner.validate(extra);
            fail("extra fields must be rejected");
        } catch (IllegalArgumentException expected) {
            assertTrue(expected.getMessage().contains("حقول"));
        }
    }
}
