package com.islamfreeagent.app;
import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
public class AgentTaskToolRunnerTest {
    @Rule public TemporaryFolder temporary = new TemporaryFolder();

    @Test public void writesAndReadsBackMultipleArabicFilesExactly() throws Exception {
        String first="الأول", second="الثاني";
        JSONObject plan=new JSONObject().put("action","write_and_read_text_files").put("files",new JSONArray()
            .put(new JSONObject().put("filename","first.txt").put("content",first))
            .put(new JSONObject().put("filename","second.txt").put("content",second)));
        JSONObject result=new AgentTaskToolRunner(temporary.getRoot()).execute(plan);
        assertTrue(result.getBoolean("verified"));
        JSONArray files=result.getJSONArray("files"); assertEquals(2,files.length());
        assertEquals(first,files.getJSONObject(0).getString("content"));
        assertEquals(second,files.getJSONObject(1).getString("content"));
        assertEquals(first,new String(Files.readAllBytes(new File(temporary.getRoot(),"first.txt").toPath()),StandardCharsets.UTF_8));
        assertEquals(second,new String(Files.readAllBytes(new File(temporary.getRoot(),"second.txt").toPath()),StandardCharsets.UTF_8));
    }

    @Test public void preservesLegacySingleFilePlan() throws Exception {
        JSONObject plan=new JSONObject().put("action","write_and_read_text_file").put("filename","test.txt").put("content","مرحبا إسلام");
        JSONObject result=new AgentTaskToolRunner(temporary.getRoot()).execute(plan);
        assertTrue(result.getBoolean("verified"));
        assertEquals("مرحبا إسلام",result.getJSONArray("files").getJSONObject(0).getString("content"));
    }

    @Test public void rejectsTraversalDuplicateNamesAndUnknownActions() throws Exception {
        JSONObject traversal=new JSONObject().put("action","write_and_read_text_files").put("files",new JSONArray()
            .put(new JSONObject().put("filename","../escape.txt").put("content","blocked")));
        try { AgentTaskToolRunner.validate(traversal); fail("path traversal must be rejected"); }
        catch(IllegalArgumentException expected) { assertTrue(expected.getMessage().contains("اسم الملف")); }
        JSONObject duplicate=new JSONObject().put("action","write_and_read_text_files").put("files",new JSONArray()
            .put(new JSONObject().put("filename","same.txt").put("content","a"))
            .put(new JSONObject().put("filename","same.txt").put("content","b")));
        try { AgentTaskToolRunner.validate(duplicate); fail("duplicate names must be rejected"); }
        catch(IllegalArgumentException expected) { assertTrue(expected.getMessage().contains("مكرر")); }
        try { AgentTaskToolRunner.validate(new JSONObject().put("action","run_shell")); fail("unknown action must be rejected"); }
        catch(IllegalArgumentException expected) { }
    }

    @Test public void rejectsExtraFieldsAndEmptyFileLists() throws Exception {
        JSONObject extra=new JSONObject().put("action","write_and_read_text_files").put("files",new JSONArray()).put("command","rm -rf /");
        try { AgentTaskToolRunner.validate(extra); fail("extra fields must be rejected"); }
        catch(IllegalArgumentException expected) { assertTrue(expected.getMessage().contains("حقول")); }
        JSONObject empty=new JSONObject().put("action","write_and_read_text_files").put("files",new JSONArray());
        try { AgentTaskToolRunner.validate(empty); fail("empty file list must be rejected"); }
        catch(IllegalArgumentException expected) { assertTrue(expected.getMessage().contains("20")); }
    }
}
