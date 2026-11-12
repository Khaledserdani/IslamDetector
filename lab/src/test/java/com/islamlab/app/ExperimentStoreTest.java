package com.islamlab.app;

import android.content.Context;\nimport android.content.ContentValues;\nimport android.database.sqlite.SQLiteDatabase;

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


    @Test public void dataSurvivesClosingAndReopeningTheDatabaseHelper() {
        String csv = "source_type,user_provided\nacquisition_origin,user_entry_or_file_import\nmeasurement_status,not_verified_as_device_measurement\nindex,value\n1,4.0\n2,5.0\n";
        assertTrue(store.save("persist-1", "قياس محفوظ", csv, 9876L));
        store.close();
        store = new ExperimentStore(context);
        ExperimentStore.Record restored = store.get("persist-1");
        assertNotNull(restored);
        assertEquals("قياس محفوظ", restored.name);
        assertEquals(csv, restored.csv);
        assertEquals("user_provided", restored.sourceType);
        assertEquals(9876L, restored.createdEpochMs);
    }


    @Test public void rejectsBlankRenameAndNullLegacySource() {
        assertFalse(store.rename("missing", ""));
        assertFalse(store.rename("missing", "   "));
        assertFalse(store.rename("", "اسم"));
        assertEquals(0, store.migrateLegacy(null));
        assertEquals(0, store.migrateLegacy(new HashMap<>()));
        assertEquals(0, store.count());
    }

    @Test public void rejectsInvalidRecords() {
        assertFalse(store.save("", "اسم", "csv", 1L));
        assertFalse(store.save("id", "", "csv", 1L));
        assertFalse(store.save("id", "اسم", "", 1L));
        assertNull(store.get("missing"));
        assertEquals(0, store.count());
    }

    @Test public void upgradesVersionOneDatabaseWithoutLosingRawRecords() {
        java.io.File dbFile = context.getDatabasePath("islam_lab_experiments.db");
        SQLiteDatabase oldDb = SQLiteDatabase.openOrCreateDatabase(dbFile, null);
        oldDb.execSQL("CREATE TABLE experiments (id TEXT PRIMARY KEY NOT NULL, name TEXT NOT NULL, csv TEXT NOT NULL, source_type TEXT NOT NULL, acquisition_origin TEXT NOT NULL, measurement_status TEXT NOT NULL, created_epoch_ms INTEGER NOT NULL, updated_epoch_ms INTEGER NOT NULL)");
        String csv = "schema_version,1.1\nsource_type,synthetic\nacquisition_origin,generated_by_lab_model\nmeasurement_status,not_a_hardware_measurement\nunit,mV\nindex,value\n1,10\n2,8\n";
        ContentValues row = new ContentValues();
        row.put("id", "old-row"); row.put("name", "سجل قديم"); row.put("csv", csv);
        row.put("source_type", "synthetic"); row.put("acquisition_origin", "generated_by_lab_model");
        row.put("measurement_status", "not_a_hardware_measurement");
        row.put("created_epoch_ms", 111L); row.put("updated_epoch_ms", 222L);
        oldDb.insertOrThrow("experiments", null, row);
        oldDb.setVersion(1);
        oldDb.close();

        ExperimentStore upgraded = new ExperimentStore(context);
        ExperimentStore.Record restored = upgraded.get("old-row");
        assertNotNull(restored);
        assertEquals(csv, restored.csv);
        assertEquals("سجل قديم", restored.name);
        assertEquals("1.1", restored.schemaVersion);
        assertEquals("mV", restored.measurementUnit);
        assertEquals(2, restored.sampleCount);
        assertEquals(1, upgraded.count());
        upgraded.close();
    }

    @Test public void filtersRecordsBySourceAndVerification() {
        String synthetic = "schema_version,1.1\nsource_type,synthetic\nmeasurement_status,not_a_hardware_measurement\nindex,value\n1,3\n2,2\n";
        String provided = "schema_version,1.1\nsource_type,user_provided\nmeasurement_status,reviewed\nindex,value\n1,5\n2,4\n";
        assertTrue(store.save("syn", "اصطناعي", synthetic, 1L));
        assertTrue(store.save("usr", "مستخدم", provided, 2L));
        assertEquals(1, store.listBySource("synthetic").size());
        assertEquals(1, store.listByVerification("reviewed").size());
    }

}
