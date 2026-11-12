package com.islamlab.app;

import android.content.Context;

import org.junit.After;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
public class ExperimentStoreTest {
    private Context context;
    private ExperimentStore store;

    @Before public void setUp() {
        context = RuntimeEnvironment.getApplication();
        context.deleteDatabase("islam_lab_experiments.db");
        store = new ExperimentStore(context);
    }

    @After public void tearDown() {
        store.close();
        context.deleteDatabase("islam_lab_experiments.db");
    }

    @Test public void savesAndRestoresExperimentWithProvenance() {
        String csv = "schema_version,1.1\nsource_type,synthetic\nacquisition_origin,generated_by_lab_model\nmeasurement_status,not_a_hardware_measurement\nunit,mV\nindex,value\n1,10.0\n2,8.0\n";
        assertTrue(store.save("exp-1", "اختبار اضمحلال", csv, 1234L));
        ExperimentStore.Record record = store.get("exp-1");
        assertNotNull(record);
        assertEquals("اختبار اضمحلال", record.name);
        assertEquals(csv, record.csv);
        assertEquals("synthetic", record.sourceType);
        assertEquals("generated_by_lab_model", record.acquisitionOrigin);
        assertEquals("not_a_hardware_measurement", record.measurementStatus);
        assertEquals(1234L, record.createdEpochMs);
        assertEquals(1, store.count());
    }

    @Test public void listsNewestFirstAndSupportsRenameAndDelete() {
        assertTrue(store.save("old", "قديم", "source_type,user_provided\n", 10L));
        assertTrue(store.save("new", "جديد", "source_type,synthetic\n", 20L));
        List<ExperimentStore.Record> records = store.list();
        assertEquals(2, records.size());
        assertEquals("new", records.get(0).id);
        assertTrue(store.rename("new", "اسم معدل"));
        assertEquals("اسم معدل", store.get("new").name);
        assertTrue(store.delete("old"));
        assertFalse(store.delete("old"));
        assertEquals(1, store.count());
    }

    @Test public void legacyMigrationPreservesRowsAndIsIdempotent() {
        Map<String, Object> legacy = new HashMap<>();
        legacy.put("experiment_12345", "source_type,user_provided\nacquisition_origin,user_entry_or_file_import\nmeasurement_status,not_verified_as_device_measurement\nindex,value\n1,1\n2,2\n");
        legacy.put("name_experiment_12345", "تجربة قديمة");
        assertEquals(1, store.migrateLegacy(legacy));
        assertEquals(0, store.migrateLegacy(legacy));
        ExperimentStore.Record record = store.get("experiment_12345");
        assertNotNull(record);
        assertEquals("تجربة قديمة", record.name);
        assertEquals(12345L, record.createdEpochMs);
        assertEquals("user_provided", record.sourceType);
        assertEquals(1, store.count());
    }

    @Test public void rejectsInvalidRecords() {
        assertFalse(store.save("", "اسم", "csv", 1L));
        assertFalse(store.save("id", "", "csv", 1L));
        assertFalse(store.save("id", "اسم", "", 1L));
        assertNull(store.get("missing"));
        assertEquals(0, store.count());
    }
}
