import importlib.util
import ipaddress
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = ROOT / "tools"
DEPLOY_SCHEMA = ROOT / "skills" / "deploy-action" / "references" / "config-schema.md"
PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
]


class PublishSafetyTests(unittest.TestCase):
    def _load_module(self, filename: str, module_name: str):
        path = TOOLS_DIR / filename
        self.assertTrue(path.exists(), f"Missing tool script: {path}")
        spec = importlib.util.spec_from_file_location(module_name, path)
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module

    def test_run_build_masks_sshpass_password_in_log_command(self):
        module = self._load_module("run_build.py", "run_build")
        formatted = module.format_command_for_log(["sshpass", "-p", "topsecret", "ssh", "root@board"])
        self.assertIn("***", formatted)
        self.assertNotIn("topsecret", formatted)

    def test_run_deploy_masks_sshpass_password_in_log_command(self):
        module = self._load_module("run_deploy.py", "run_deploy")
        formatted = module.format_command_for_log(["sshpass", "-p", "deploysecret", "scp", "artifact", "root@board:/tmp/app"])
        self.assertIn("***", formatted)
        self.assertNotIn("deploysecret", formatted)

    def test_deploy_schema_does_not_publish_private_ip_examples(self):
        self.assertTrue(DEPLOY_SCHEMA.exists(), f"Missing schema doc: {DEPLOY_SCHEMA}")
        text = DEPLOY_SCHEMA.read_text(encoding="utf-8")
        candidates = re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", text)
        for candidate in candidates:
            address = ipaddress.ip_address(candidate)
            self.assertFalse(
                any(address in network for network in PRIVATE_NETWORKS),
                f"RFC1918 private IP leaked in publishable docs: {candidate}",
            )


if __name__ == "__main__":
    unittest.main()
