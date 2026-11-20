import unittest
from lab_catalog import list_laboratories, select_laboratory


class LaboratoryCatalogTests(unittest.TestCase):
    def test_catalog_covers_multiple_engineering_and_science_domains(self):
        domains = {lab.domain for lab in list_laboratories()}
        self.assertTrue({"electronics", "software", "embedded", "signals",
                         "science", "mechanical", "thermal", "materials",
                         "data", "research"}.issubset(domains))

    def test_only_implemented_laboratories_can_be_selected(self):
        lab = select_laboratory("electronics", "dc_resistive_network")
        self.assertEqual(lab.status, "implemented")
        with self.assertRaises(NotImplementedError):
            select_laboratory("electronics", "transient_circuits")

    def test_no_unregistered_lab_can_be_loaded(self):
        with self.assertRaises(LookupError):
            select_laboratory("chemistry", "anything")


if __name__ == "__main__":
    unittest.main()
