import importlib
import os
import unittest

import src.config as config


class SettingsEnvironmentTest(unittest.TestCase):
    def test_settings_reads_environment_values(self):
        old_env = {
            key: os.environ.get(key)
            for key in ["OPIK_API_KEY", "OPIK_WORKSPACE", "OPIK_PROJECT_NAME"]
        }

        try:
            os.environ.update(
                {
                    "OPIK_API_KEY": "demo_key",
                    "OPIK_WORKSPACE": "demo_workspace",
                    "OPIK_PROJECT_NAME": "demo_project",
                }
            )

            importlib.reload(config)
            settings = config.Settings()

            self.assertEqual(settings.opik_api_key, "demo_key")
            self.assertEqual(settings.opik_workspace, "demo_workspace")
            self.assertEqual(settings.opik_project_name, "demo_project")
        finally:
            for key, value in old_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
            importlib.reload(config)


if __name__ == "__main__":
    unittest.main()
