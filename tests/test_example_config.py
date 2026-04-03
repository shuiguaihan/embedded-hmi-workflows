import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_CONFIG = ROOT / "project_ai" / "build-deploy.skill.example.yaml"


class ExampleConfigTests(unittest.TestCase):
    def test_example_build_deploy_config_exists_and_is_json_compatible(self):
        self.assertTrue(EXAMPLE_CONFIG.exists(), f"Missing example config: {EXAMPLE_CONFIG}")
        config = json.loads(EXAMPLE_CONFIG.read_text(encoding="utf-8"))

        self.assertEqual(config["version"], 1)
        self.assertIn("logs_dir", config)
        self.assertIn("secrets_file", config)

        build = config["build"]
        self.assertEqual(build["host"]["kind"], "local")
        self.assertIn("working_dir", build)
        self.assertIn("command", build)
        self.assertIn("artifact_path", build)

        deploy = config["deploy"]
        self.assertIn("local_artifact", deploy)
        self.assertEqual(deploy["target"]["kind"], "ssh")
        self.assertIn("host", deploy["target"])
        self.assertIn("user", deploy["target"])
        self.assertIn("remote_final_path", deploy["copy"])


if __name__ == "__main__":
    unittest.main()
