import importlib.util
import unittest
from pathlib import Path

spec=importlib.util.spec_from_file_location('ci_simulator',Path(__file__).resolve().parents[1]/'scripts/ci-simulator.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)

class RunnerSelectionTests(unittest.TestCase):
    def test_current_hosted_iphone_is_accepted_on_exact_runtime(self):
        device={'udid':'test-device','name':'iPhone 18 Pro','isAvailable':True,
                'deviceTypeIdentifier':'com.apple.CoreSimulator.SimDeviceType.iPhone-18-Pro'}
        devices={'devices':{'com.apple.CoreSimulator.SimRuntime.iOS-27-0':[device]}}
        self.assertEqual(runner.select(devices),device)
        devices['devices']={'com.apple.CoreSimulator.SimRuntime.iOS-26-5':[device]}
        with self.assertRaises(ValueError):runner.select(devices)

    def test_unavailable_and_other_device_fail_closed(self):
        for available,kind in [(False,'iPhone-17'),(True,'iPad-Pro')]:
            device={'isAvailable':available,'deviceTypeIdentifier':'com.apple.CoreSimulator.SimDeviceType.'+kind}
            with self.assertRaises(ValueError):runner.select({'devices':{'com.apple.CoreSimulator.SimRuntime.iOS-27-0':[device]}})
