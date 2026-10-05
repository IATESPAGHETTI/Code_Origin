import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

import make_demo_repo  # noqa: E402


class FakeRag:
    """Stands in for the rag service: upsert-by-id store with delete/stats."""

    def __init__(self):
        self.chunks = {}
        self.index_calls = 0

    def index(self, repo, chunks):
        self.index_calls += 1
        for c in chunks:
            self.chunks[(repo, c["id"])] = c
        return {"indexed": len(chunks)}

    def delete(self, repo, source_types=None):
        doomed = [k for k, c in self.chunks.items() if k[0] == repo and (not source_types or c["source_type"] in source_types)]
        for k in doomed:
            del self.chunks[k]
        return {"deleted": len(doomed)}

    def stats(self, repo):
        counts = {}
        for (r, _), c in self.chunks.items():
            if r == repo:
                counts[c["source_type"]] = counts.get(c["source_type"], 0) + 1
        return {"repo": repo, "counts": counts, "total": sum(counts.values())}

    def of_type(self, t):
        return [c for c in self.chunks.values() if c["source_type"] == t]


@pytest.fixture(scope="session")
def demo(tmp_path_factory):
    out = tmp_path_factory.mktemp("demo")
    shas = make_demo_repo.build(out)
    return {"repo": str(out / "repo"), "fixtures": str(out / "fixtures.json"), "shas": shas, "dir": out}


@pytest.fixture()
def fake_rag():
    return FakeRag()


def git(path, *args):
    return subprocess.run(["git", *args], cwd=path, check=True, capture_output=True, text=True).stdout
