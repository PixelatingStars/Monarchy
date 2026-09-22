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


class PlayDetectionTests(unittest.TestCase):
    def test_exact_play_box_with_best_confidence_is_selected(self):
        data = {
            "text": ["Changelogs", "Play", "PLAY!"],
            "conf": [95, 42, 89],
            "left": [1, 20, 30], "top": [2, 40, 50],
            "width": [80, 60, 70], "height": [12, 20, 24],
        }
        confidence, box = monarchy.play_box_from_ocr(data)
        self.assertEqual(confidence, 89)
        self.assertEqual(box, (30, 50, 70, 24))

    def test_low_confidence_play_is_rejected(self):
        confidence, box = monarchy.play_box_from_ocr({
            "text": ["Play"], "conf": [12], "left": [1], "top": [2],
            "width": [40], "height": [15],
        })
        self.assertIsNone(confidence)
        self.assertIsNone(box)


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

    def test_hell_channel_is_not_overridden_by_stale_window_title(self):
        instance = "12345678-1234-1234-1234-123456789abc"
        server = monarchy.MonarchyServer()
        server.channel = ("HELL", "BIOME")
        payload = {
            "url": f"roblox://experiences/start?placeId={monarchy.PLACE_ID}&gameInstanceId={instance}",
            "targetBiome": "HELL",
        }
        with patch.object(monarchy, "discord_title_channel", return_value=("CORRUPTION", "BIOME")), \
             patch.object(server, "can_start", return_value=False):
            self.assertEqual(server.submit_link(payload), 409)
        self.assertEqual(server.pending[2], "HELL")

    def test_corruption_channel_remains_accepted(self):
        instance = "abcdefab-1234-1234-1234-abcdefabcdef"
        server = monarchy.MonarchyServer()
        server.channel = ("CORRUPTION", "BIOME")
        payload = {
            "url": f"roblox://experiences/start?placeId={monarchy.PLACE_ID}&gameInstanceId={instance}",
            "targetBiome": "CORRUPTION",
        }
        with patch.object(server, "can_start", return_value=False):
            self.assertEqual(server.submit_link(payload), 409)
        self.assertEqual(server.pending[2], "CORRUPTION")

    def test_only_newest_new_desktop_link_is_selected(self):
        def payload(instance):
            return {"url": (
                f"roblox://experiences/start?placeId={monarchy.PLACE_ID}"
                f"&gameInstanceId={instance}"
            )}
        first = "11111111-1111-1111-1111-111111111111"
        second = "22222222-2222-2222-2222-222222222222"
        third = "33333333-3333-3333-3333-333333333333"
        known = {f"public:{first}"}
        selected = monarchy.newest_unseen_desktop_candidate(
            [payload(first), payload(second), payload(third)], known
        )
        self.assertIn(third, selected["url"])
        self.assertEqual(known, {f"public:{first}", f"public:{second}", f"public:{third}"})


if __name__ == "__main__":
    unittest.main()
