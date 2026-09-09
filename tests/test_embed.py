import importlib.util
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load_embed():
    spec = importlib.util.spec_from_file_location("embed", ROOT / "tools" / "embed.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _extract_cipher(generated, name):
    """Return the raw bytes of an `extern const unsigned char <name>[] = {...}` array."""
    m = re.search(name + r"\[\]\s*=\s*\{([^}]*)\}", generated)
    if not m:
        return None
    return bytes(int(tok, 16) for tok in re.findall(r"0x[0-9A-Fa-f]{2}", m.group(1)))


class TestEmbed(unittest.TestCase):
    def _assert_embedded_matches_asset(self, asset_rel, cipher_name, seed_offset):
        """The committed cipher must equal what embed.py would emit for the current asset.

        The build skips a full embed.py regen when assets/rewriter_builtin.json is
        absent, so the committed resources_generated.cpp is the source of truth for
        embedded bytes. This guards against an edited asset drifting from its
        embedded copy (e.g. dashboard.html gaining a new prompt-mode option).
        """
        embed = _load_embed()
        asset = (ROOT / asset_rel).read_bytes().replace(b"\r\n", b"\n")
        expected, _ = embed.encrypt(asset, embed.KEY_SEED + seed_offset)
        generated = (ROOT / "src" / "resources_generated.cpp").read_text(encoding="utf-8")
        committed = _extract_cipher(generated, cipher_name)
        self.assertIsNotNone(committed, cipher_name + " not found in resources_generated.cpp")
        self.assertEqual(committed, expected,
                         asset_rel + " drifted from its embedded copy; run tools/embed.py")

    def test_embedded_dashboard_matches_asset(self):
        # seed offset must match tools/embed.py's emit_var('kDashboardHtml', ..., +0x3000)
        self._assert_embedded_matches_asset("assets/dashboard.html", "kDashboardHtmlCipher", 0x3000)

    def test_embedded_gpt6_prompt_matches_asset(self):
        self._assert_embedded_matches_asset("assets/prompt-gpt6-instruct.md", "kAgentsGpt6Cipher", 0x9000)
    def test_missing_optional_rewriter_config_emits_valid_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "resources_generated.cpp"
            subprocess.run(
                [sys.executable, str(ROOT / "tools" / "embed.py"), tmp, out],
                check=True,
                capture_output=True,
                text=True,
            )
            generated = out.read_text(encoding="utf-8")
            match = re.search(r"kRewriterBuiltinCipherLen = (\d+)", generated)
            self.assertIsNotNone(match)
            self.assertGreater(int(match.group(1)), 0)

    def test_gpt6_prompt_is_embedded(self):
        prompt = (ROOT / "assets" / "prompt-gpt6-instruct.md").read_bytes().replace(b"\r\n", b"\n")
        self.assertGreater(len(prompt), 0)
        generated = (ROOT / "src" / "resources_generated.cpp").read_text(encoding="utf-8")
        match = re.search(r"kAgentsGpt6CipherLen = (\d+)", generated)
        self.assertIsNotNone(match)
        self.assertEqual(int(match.group(1)), len(prompt))

    def test_qa_json_is_valid_and_embedded(self):
        qa = __import__("json").loads((ROOT / "assets" / "qa.json").read_text(encoding="utf-8"))
        self.assertTrue(qa["items"])
        self.assertTrue(all(item.get("question") and item.get("answer") for item in qa["items"]))
        generated = (ROOT / "src" / "resources_generated.cpp").read_text(encoding="utf-8")
        match = re.search(r"kQaJsonCipherLen = (\d+)", generated)
        self.assertIsNotNone(match)
        self.assertGreater(int(match.group(1)), 0)


if __name__ == "__main__":
    unittest.main()
