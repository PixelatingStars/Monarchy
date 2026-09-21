import tempfile
import unittest
import sys
import types
from pathlib import Path
from unittest.mock import patch

# The build target includes Tk. The Linux validation host does not, so provide
# only the import-time surface needed to test platform-neutral logic.
try:
    import tkinter  # noqa: F401
except ImportError:
    tkinter_stub = types.ModuleType("tkinter")
    tkinter_stub.Tk = object
    tkinter_stub.messagebox = types.SimpleNamespace()
    tkinter_stub.ttk = types.SimpleNamespace()
    sys.modules["tkinter"] = tkinter_stub
    sys.modules["tkinter.ttk"] = tkinter_stub.ttk
    sys.modules["tkinter.messagebox"] = tkinter_stub.messagebox

import monarchy


class LinkParsingTests(unittest.TestCase):
    def test_public_instance(self):
        instance = "12345678-1234-1234-1234-123456789abc"
        parsed = monarchy.parse_link(
            f"roblox://experiences/start?placeId={monarchy.PLACE_ID}&gameInstanceId={instance}"
        )
        self.assertEqual(parsed[0], f"public:{instance}")

    def test_private_server(self):
        parsed = monarchy.parse_link(
            f"https://www.roblox.com/games/{monarchy.PLACE_ID}/Sols-RNG?privateServerLinkCode=Abc_123"
        )
        self.assertEqual(parsed[0], "private:abc_123")

    def test_share_link(self):
        code = "0123456789abcdef0123456789abcdef"
        parsed = monarchy.parse_link(f"https://www.roblox.com/share?code={code}&type=Server")
        self.assertEqual(parsed, (f"share:{code}", f"roblox://navigation/share_links?code={code}&type=Server"))

    def test_other_place_rejected(self):
        self.assertIsNone(monarchy.parse_link(
            "roblox://experiences/start?placeId=1&gameInstanceId=12345678-1234-1234-1234-123456789abc"
        ))


class SettingsTests(unittest.TestCase):
    def test_obsolete_workflow_settings_are_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            settings_file = Path(directory) / "settings.json"
            settings_file.write_text('{"mode":"OLD","points":{"inventory":[1,2]}}')
            with patch.object(monarchy, "DATA_DIR", Path(directory)), patch.object(monarchy, "SETTINGS_FILE", settings_file):
                settings = monarchy.load_settings()
            self.assertEqual(settings, {"close_roblox_on_stop": True})


class UpdateTests(unittest.TestCase):
    def test_semantic_versions(self):
        self.assertEqual(monarchy.version_key("v0.2.2"), (0, 2, 2))
        self.assertIsNone(monarchy.version_key("latest"))


class DiscordDesktopTests(unittest.TestCase):
    def test_accessible_message_candidate(self):
        instance = "12345678-1234-1234-1234-123456789abc"
        message = (
            "Corruption Biome Started 7/20 "
            f"roblox://experiences/start?placeId={monarchy.PLACE_ID}&gameInstanceId={instance}"
        )
        candidates = monarchy.discord_desktop_candidates(
            [message], (monarchy.MIXED_CHANNEL, "BIOME")
        )
        self.assertEqual(candidates[0]["targetBiome"], "CORRUPTION")
        self.assertEqual(candidates[0]["playerCount"], 7)

    def test_mixed_channel_rejects_message_without_biome(self):
        instance = "12345678-1234-1234-1234-123456789abc"
        message = f"roblox://experiences/start?placeId={monarchy.PLACE_ID}&gameInstanceId={instance}"
        self.assertEqual(monarchy.discord_desktop_candidates(
            [message], (monarchy.MIXED_CHANNEL, "BIOME")
        ), [])


if __name__ == "__main__":
    unittest.main()
