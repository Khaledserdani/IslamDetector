"""Static regression guards for Rev A's safe, logic-only bring-up defaults."""

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
RP_MAIN = ROOT / "firmware/rp2040_timing_test/src/main.c"
RP_CMAKE = ROOT / "firmware/rp2040_timing_test/CMakeLists.txt"
ADC_DRIVER = ROOT / "firmware/rp2040_timing_test/src/ads8861_capture.c"
UART_KCONFIG = ROOT / "firmware/esp32_s3_bridge/main/Kconfig"
ESP32_SDKCONFIG_DEFAULTS = ROOT / "firmware/esp32_s3_bridge/sdkconfig.defaults"
ESP32_WORKFLOW = ROOT / ".github/workflows/main.yml"
UART_APP_MAIN = ROOT / "firmware/esp32_s3_bridge/main/app_main.c"
UART_DRIVER = ROOT / "firmware/esp32_s3_bridge/components/rev_a_uart_bridge/rev_a_uart_bridge.c"
TX_INTERLOCK_SPEC = ROOT / "docs/engineering/REV_A_TX_INTERLOCK_SPEC_AR.md"
TX_CURRENT_LIMIT_CANDIDATES = ROOT / "docs/engineering/REV_A_TX_CURRENT_LIMIT_CANDIDATES_AR.md"
TX_CLAMP_SCHEMATIC = ROOT / "docs/engineering/REV_A_TX_POWER_STAGE_BLOCK_SCHEMATIC_AR.md"
TX_CLAMP_COMPARISON = ROOT / "docs/engineering/REV_A_TX_CLAMP_COMPARISON_AR.md"


class RevASafetyGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rp_main = RP_MAIN.read_text(encoding="utf-8")
        cls.rp_cmake = RP_CMAKE.read_text(encoding="utf-8")
        cls.adc_driver = ADC_DRIVER.read_text(encoding="utf-8")
        cls.kconfig = UART_KCONFIG.read_text(encoding="utf-8")
        cls.esp32_sdkconfig_defaults = ESP32_SDKCONFIG_DEFAULTS.read_text(encoding="utf-8")
        cls.esp32_workflow = ESP32_WORKFLOW.read_text(encoding="utf-8")
        cls.app_main = UART_APP_MAIN.read_text(encoding="utf-8")
        cls.uart_driver = UART_DRIVER.read_text(encoding="utf-8")
        cls.tx_interlock_spec = TX_INTERLOCK_SPEC.read_text(encoding="utf-8")
        cls.tx_current_limit_candidates = TX_CURRENT_LIMIT_CANDIDATES.read_text(encoding="utf-8")
        cls.tx_clamp_schematic = TX_CLAMP_SCHEMATIC.read_text(encoding="utf-8")
        cls.tx_clamp_comparison = TX_CLAMP_COMPARISON.read_text(encoding="utf-8")

    def test_ads8861_capture_is_disabled_in_default_rp2040_firmware(self):
        self.assertIn("#define ENABLE_ADS8861_CAPTURE 0", self.rp_main)

    def test_adc_capture_requires_the_documented_system_clock(self):
        self.assertIn("clock_get_hz(clk_sys) != ADS8861_SYS_CLOCK_HZ", self.adc_driver)
        self.assertIn("#define ADS8861_SYS_CLOCK_HZ 125000000u", self.adc_driver)

    def test_uart_bridge_is_disabled_and_gpio_defaults_are_unassigned(self):
        self.assertRegex(self.kconfig, r"config REV_A_UART_ENABLE[\s\S]*?default n")
        self.assertRegex(self.kconfig, r"config REV_A_UART_TX_GPIO[\s\S]*?default -1")
        self.assertRegex(self.kconfig, r"config REV_A_UART_RX_GPIO[\s\S]*?default -1")

    def test_esp32_s3_target_is_pinned_in_defaults_and_ci(self):
        self.assertIn('CONFIG_IDF_TARGET="esp32s3"', self.esp32_sdkconfig_defaults)
        self.assertIn("idf.py set-target esp32s3", self.esp32_workflow)
        self.assertIn('CONFIG_IDF_TARGET_ESP32S3=y', self.esp32_workflow)
        self.assertIn("--chip esp32s3", self.esp32_workflow)
        self.assertIn("IslamDetector-RevA-ESP32S3-BUILD-ONLY", self.esp32_workflow)

    def test_enabling_uart_without_verified_gpio_fails_the_build(self):
        self.assertIn("#if CONFIG_REV_A_UART_ENABLE", self.app_main)
        self.assertIn("#if CONFIG_REV_A_UART_TX_GPIO < 0 || CONFIG_REV_A_UART_RX_GPIO < 0", self.app_main)
        self.assertIn("#error", self.app_main)

    def test_uart_driver_rejects_console_port_and_invalid_or_shared_pins(self):
        self.assertIn("cfg->uart_port <= UART_NUM_0", self.uart_driver)
        self.assertIn("cfg->tx_gpio_num < 0", self.uart_driver)
        self.assertIn("cfg->rx_gpio_num < 0", self.uart_driver)
        self.assertIn("cfg->tx_gpio_num == cfg->rx_gpio_num", self.uart_driver)

    def test_logic_only_timing_output_starts_low_and_requires_manual_start(self):
        self.assertIn("gpio_put(TX_TEST_PIN, 0);", self.rp_main)
        self.assertIn("Safe boot: no pulse is generated until command R.", self.rp_main)
        self.assertIn("if (ch == 'R' || ch == 'r')", self.rp_main)
        self.assertIn("Do NOT connect GP4 to a gate driver or coil.", self.rp_main)

    def test_protocol_start_is_rejected_until_a_hardware_tx_interlock_exists(self):
        self.assertIn("case REV_A_TYPE_START:", self.rp_main)
        self.assertIn("REV_A_ACK_STATUS_REJECTED", self.rp_main)
        self.assertIn("REV_A_ACK_REASON_TX_NOT_ARMED", self.rp_main)

    def test_protocol_uart0_is_not_shared_with_stdio_console(self):
        self.assertIn("pico_enable_stdio_uart(islam_rev_a_timing_test 0)", self.rp_cmake)
        self.assertIn("pico_enable_stdio_usb(islam_rev_a_timing_test 1)", self.rp_cmake)

    def test_tx_interlock_spec_requires_independent_hardware_cutoff(self):
        self.assertIn("Hardware one-shot", self.tx_interlock_spec)
        self.assertIn("Fast analog comparator", self.tx_interlock_spec)
        self.assertIn("fault latch", self.tx_interlock_spec)
        self.assertIn("Gate OFF", self.tx_interlock_spec)

    def test_tx_clamp_forbids_unidirectional_tvs_directly_across_coil(self):
        self.assertIn("TVS1 bidirectional", self.tx_clamp_schematic)
        self.assertIn("ممنوع TVS أحادي الاتجاه مباشرة عبر الملف", self.tx_clamp_schematic)
        self.assertIn("blocking diode", self.tx_clamp_comparison)
        self.assertIn("SMBJ18CA", self.tx_clamp_comparison)

    def test_current_limit_candidate_records_offset_and_delay_tradeoff(self):
        self.assertIn("TLV3201", self.tx_current_limit_candidates)
        self.assertIn("55ns max", self.tx_current_limit_candidates)
        self.assertIn("4mV", self.tx_current_limit_candidates)
        self.assertIn("لا يعتمد comparator أو الشنت بعد", self.tx_current_limit_candidates)


if __name__ == "__main__":
    unittest.main()
