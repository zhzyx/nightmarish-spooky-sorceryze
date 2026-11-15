"""多宝仓库导入来源校验：协议、凭据、主机白名单与本机路径开关。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from git_service import ValidationError, validate_import_source


class ImportSourceUrlTests(unittest.TestCase):
    def test_accepts_https_and_ssh_urls(self) -> None:
        for source in (
            "https://github.com/owner/repo.git",
            "https://git.example.com:8443/group/repo.git",
            "ssh://git@github.com/owner/repo.git",
            "git://git.example.com/repo.git",
        ):
            with self.subTest(source=source):
                self.assertEqual(validate_import_source(source), source)

    def test_rejects_unknown_scheme(self) -> None:
        for source in ("http://example.com/repo.git", "ftp://example.com/repo.git", "javascript:alert(1)"):
            with self.subTest(source=source):
                with self.assertRaises(ValidationError):
                    validate_import_source(source)

    def test_rejects_embedded_credentials(self) -> None:
        for source in (
            "https://user:secret@github.com/owner/repo.git",
            "https://token@github.com/owner/repo.git",
            "ssh://git:secret@github.com/owner/repo.git",
        ):
            with self.subTest(source=source):
                with self.assertRaises(ValidationError):
                    validate_import_source(source)

    def test_requires_host(self) -> None:
        with self.assertRaises(ValidationError):
            validate_import_source("https:///owner/repo.git")

    def test_host_allowlist_is_case_insensitive(self) -> None:
        self.assertEqual(
            validate_import_source("https://GitHub.com/owner/repo.git", allowed_hosts=("github.com",)),
            "https://GitHub.com/owner/repo.git",
        )
        with self.assertRaises(ValidationError):
            validate_import_source("https://gitlab.com/owner/repo.git", allowed_hosts=("github.com",))

    def test_rejects_malformed_sources(self) -> None:
        for source in ("", "  https://github.com/x/y  ", "-https://github.com/x/y", "https://github.com/x/y\nnext"):
            with self.subTest(source=source):
                with self.assertRaises(ValidationError):
                    validate_import_source(source)
        with self.assertRaises(ValidationError):
            validate_import_source(42)  # type: ignore[arg-type]


class ImportSourceLocalTests(unittest.TestCase):
    def test_file_url_requires_explicit_local_opt_in(self) -> None:
        with self.assertRaises(ValidationError):
            validate_import_source("file:///tmp/repo.git")
        self.assertEqual(
            validate_import_source("file:///tmp/repo.git", allow_local=True),
            "file:///tmp/repo.git",
        )

    def test_local_path_requires_absolute_existing_and_opt_in(self) -> None:
        with tempfile.TemporaryDirectory(prefix="duobao-import-test-") as temporary:
            root = Path(temporary)
            with self.assertRaises(ValidationError):
                validate_import_source(str(root))
            self.assertEqual(validate_import_source(str(root), allow_local=True), str(root))
            with self.assertRaises(ValidationError):
                validate_import_source("relative/path", allow_local=True)
            with self.assertRaises(ValidationError):
                validate_import_source(str(root / "missing"), allow_local=True)


if __name__ == "__main__":
    unittest.main()
