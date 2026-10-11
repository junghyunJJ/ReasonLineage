"""The protocol: the prompt files plus protocol.json.

Every run records the protocol version and a hash of these files; paper analyses compare
only runs with the same hash.
"""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from string import Template
from typing import Any, Mapping

ROOT = Path(__file__).parent


def protocol_files(root: Path) -> list[Path]:
    return [root / "protocol.json", *sorted((root / "prompts").glob("*.md"))]


def protocol_hash(root: Path = ROOT) -> str:
    digest = hashlib.sha256()
    for path in protocol_files(root):
        digest.update(path.relative_to(root).as_posix().encode() + b"\0")
        digest.update(path.read_bytes() + b"\0")
    return digest.hexdigest()


@dataclass(frozen=True)
class ProtocolSpec:
    root: Path
    hash: str
    data: Mapping[str, Any]

    @property
    def version(self) -> str:
        return self.data["version"]

    @property
    def generations(self) -> int:
        return int(self.data["generations"])

    @property
    def margins(self) -> Mapping[str, float]:
        return self.data["margins"]

    @property
    def approaches(self) -> list[str]:
        return list(self.data["seed_approaches"])

    @property
    def answer_words(self) -> tuple[int, int]:
        low, high = self.data["answer"]["length_words"]
        return int(low), int(high)

    @property
    def open_items(self) -> tuple[int, int]:
        low, high = self.data["answer"]["open_question_items"]
        return int(low), int(high)

    @property
    def j1(self) -> Mapping[str, Any]:
        return self.data["j1"]

    @property
    def j2(self) -> Mapping[str, Any]:
        return self.data["j2"]

    def timeout(self, kind: str) -> float:
        return float(self.data["timeouts_s"][kind])

    def max_tokens(self, kind: str) -> int:
        return int(self.data["max_tokens"][kind])

    def render(self, name: str, **values: Any) -> str:
        """Fill a prompt file. Values go in as-is, so `$` or braces inside them are safe."""
        template = Template((self.root / "prompts" / f"{name}.md").read_text(encoding="utf-8"))
        return template.substitute({key: str(value) for key, value in values.items()}).strip()


def load_protocol(root: Path | None = None) -> ProtocolSpec:
    root = Path(root) if root else ROOT
    data = json.loads((root / "protocol.json").read_text(encoding="utf-8"))
    return ProtocolSpec(root=root, hash=protocol_hash(root), data=data)


PROFILES = ROOT / "profiles"


def available_profiles() -> list[str]:
    """Packaged profile names accepted by --protocol besides "default"."""
    if not PROFILES.is_dir():
        return []
    return sorted(p.name for p in PROFILES.iterdir() if (p / "protocol.json").is_file())


def resolve_protocol(value: str | None) -> tuple[Path, dict[str, str]]:
    """Folder for --protocol VALUE and the source recorded in header.json."""
    if value is None or value == "default":
        return ROOT, {"profile": "default"}
    if value in available_profiles():
        return PROFILES / value, {"profile": value}
    folder = Path(value).expanduser()
    if (folder / "protocol.json").is_file():
        folder = folder.resolve()
        return folder, {"path": str(folder)}
    names = ", ".join(["default", *available_profiles()])
    raise ValueError(f"--protocol {value!r} is neither a packaged profile ({names}) nor a folder with protocol.json")


def protocol_root_from_source(source: Mapping[str, str] | None) -> Path:
    """Folder of the protocol a run header names; headers written before --protocol existed mean the default."""
    if not source or source.get("profile") == "default":
        return ROOT
    root = PROFILES / source["profile"] if "profile" in source else Path(source["path"])
    if not (root / "protocol.json").is_file():
        raise ValueError(f"the protocol recorded in header.json is missing: {root}")
    return root
