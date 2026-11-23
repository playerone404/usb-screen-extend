"""
Automated security and vulnerability audit tests.
"""

import os
import re
import unittest
import xml.etree.ElementTree as ET

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestSecurityAudit(unittest.TestCase):
    def test_no_insecure_host_binding(self):
        """Servers must bind exclusively to 127.0.0.1 to avoid exposing screen over LAN."""
        server_files = [
            os.path.join(REPO_ROOT, "windows_screen_extend", "core", "server.py"),
            os.path.join(REPO_ROOT, "linux_screen_mirror", "core", "second_screen_server.py"),
        ]
        for sfile in server_files:
            if not os.path.exists(sfile):
                continue
            with open(sfile, "r", encoding="utf-8") as f:
                content = f.read()
                # Check for bind("0.0.0.0" or bind(("",
                self.assertNotIn('bind(("0.0.0.0"', content, f"{sfile} must not bind to 0.0.0.0")
                self.assertNotIn('bind(("",', content, f"{sfile} must not bind to INADDR_ANY")
                self.assertIn('127.0.0.1', content, f"{sfile} must explicitly bind to 127.0.0.1")

    def test_gitignore_protects_sensitive_files(self):
        """Root .gitignore must protect local credentials, keystores, and build directories."""
        gitignore_path = os.path.join(REPO_ROOT, ".gitignore")
        self.assertTrue(os.path.exists(gitignore_path), ".gitignore must exist in root")

        with open(gitignore_path, "r", encoding="utf-8") as f:
            patterns = f.read()

        essential_patterns = [
            "local.properties",
            "*.keystore",
            "*.jks",
            ".gradle",
            "__pycache__",
        ]
        for pat in essential_patterns:
            self.assertIn(pat, patterns, f".gitignore must contain {pat}")

    def test_no_hardcoded_user_paths(self):
        """Codebase must not contain personal developer user paths."""
        forbidden_patterns = [
            re.compile(r"[A-Z]:\\Users\\Playerone", re.IGNORECASE),
            re.compile(r"/home/playerone", re.IGNORECASE),
        ]

        checked_extensions = (".py", ".bat", ".vbs", ".sh", ".kt", ".xml", ".json")
        for root, _, files in os.walk(REPO_ROOT):
            if any(p in root for p in (".git", ".gradle", "build", "__pycache__", "tests")):
                continue
            for fname in files:
                if fname == "local.properties":  # local file not committed
                    continue
                if fname.endswith(checked_extensions):
                    fpath = os.path.join(root, fname)
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                        for pat in forbidden_patterns:
                            match = pat.search(content)
                            self.assertIsNone(
                                match,
                                f"Forbidden personal path found in {fpath}: {match.group(0) if match else ''}"
                            )

    def test_android_manifest_minimal_permissions(self):
        """Android app must only request INTERNET permission (no camera, mic, location, storage)."""
        manifest_path = os.path.join(REPO_ROOT, "android", "app", "src", "main", "AndroidManifest.xml")
        self.assertTrue(os.path.exists(manifest_path))

        tree = ET.parse(manifest_path)
        root = tree.getroot()

        permissions = []
        for elem in root.findall("uses-permission"):
            name = elem.attrib.get("{http://schemas.android.com/apk/res/android}name")
            if name:
                permissions.append(name)

        self.assertEqual(permissions, ["android.permission.INTERNET"])

        # allowBackup must be false
        app_elem = root.find("application")
        self.assertIsNotNone(app_elem)
        allow_backup = app_elem.attrib.get("{http://schemas.android.com/apk/res/android}allowBackup")
        self.assertEqual(allow_backup, "false")


if __name__ == "__main__":
    unittest.main()
