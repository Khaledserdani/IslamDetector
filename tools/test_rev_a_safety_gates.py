"""Static regression guards for Rev A's safe, logic-only bring-up defaults."""

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
RP_MAIN = ROOT / "firmware/rp2040_timing_test/src/main.c"
ADC_DRIVER = ROOT / "firmware/rp2040_timing_test/src/ads8861_capture.c"
UART_KCONFIG = ROOT / "firmware/esp32_s3_bridge/Kconfig.projbuild"
UART_APP_MAIN = ROOT / "firmware/esp32_s3_bridge/main/app_main.c"
UART_DRIVER = ROOT / "firmware/esp32_s3_bridge/components/rev_a_uart_bridge/rev_a_uart_bridge.c"


class RevASafetyGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rp_main = RP_MAIN.read_text(encoding="utf-8")
        cls.adc_driver = ADC_DRIVER.read_text(encoding="utf-8")
        cls.kconfig = UART_KCONFIG.read_text(encoding="utf-8")
        cls.app_main = UART_APP_MAIN.read_text(encoding="utf-8")
        cls.uart_driver = UART_DRIVER.read_text(encoding="utf-8")

    def test_ads8861_capture_is_disabled_in_default_rp2040_firmware(self):
        self.assertIn("#define ENABLE_ADS8861_CAPTURE 0", self.rp_main)

    def test_adc_capture_requires_the_documented_system_clock(self):
        self.assertIn("clock_get_hz(clk_sys) != ADS8861_SYS_CLOCK_HZ", self.adc_driver)
        self.assertIn("#define ADS8861_SYS_CLOCK_HZ 125000000u", self.adc_driver)

    def test_uart_bridge_is_disabled_and_gpio_defaults_are_unassigned(self):
        self.assertRegex(self.kconfig, r"config REV_A_UART_ENABLE[\s\S]*?default n")
        self.assertRegex(self.kconfig, r"config REV_A_UART_TX_GPIO[\s\S]*?default -1")
        self.assertRegex(self.kconfig, r"config REV_A_UART_RX_GPIO[\s\S]*?default -1")

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


if __name__ == "__main__":
    unittest.main()
