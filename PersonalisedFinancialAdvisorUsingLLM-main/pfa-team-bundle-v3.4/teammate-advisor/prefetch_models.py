"""Downloads the models warmup.py needs, in their own image layer, before warmup.py runs.

Each download resumes where it stopped and retries, so a slow or unstable connection does not fail
the build (Chroma's own downloader gives up after ~1 minute and starts again from zero). Once this
layer has been built, Docker caches it: rebuilding after a code change never downloads these again.
"""
import hashlib
import os
import sys
import tarfile
import time
import urllib.request
from pathlib import Path

ATTEMPTS = 8


def retry(what, fn):
    for attempt in range(1, ATTEMPTS + 1):
        try:
            return fn()
        except Exception as exc:  # network errors of every kind: retry, keeping what was downloaded
            if attempt == ATTEMPTS:
                sys.exit(f"[prefetch] {what}: giving up after {ATTEMPTS} attempts ({exc})")
            wait = min(60, 5 * attempt)
            print(f"[prefetch] {what}: attempt {attempt} failed ({exc}); retrying in {wait}s", flush=True)
            time.sleep(wait)


# 1. Chroma's local embedding model (all-MiniLM-L6-v2, ONNX, 79 MB) - same URL, path and checksum
#    as chromadb.utils.embedding_functions.ONNXMiniLM_L6_V2, so Chroma finds it and skips its download.
CHROMA_URL = "https://chroma-onnx-models.s3.amazonaws.com/all-MiniLM-L6-v2/onnx.tar.gz"
CHROMA_SHA256 = "913d7300ceae3b2dbc2c50d1de4baacab4be7b9380491c27fab7418616a16ec3"
CHROMA_DIR = Path.home() / ".cache" / "chroma" / "onnx_models" / "all-MiniLM-L6-v2"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def download_resumable(url, dest):
    have = dest.stat().st_size if dest.exists() else 0
    req = urllib.request.Request(url, headers={"Range": f"bytes={have}-"} if have else {})
    with urllib.request.urlopen(req, timeout=120) as resp:
        if have and resp.status != 206:  # server ignored the range: start again
            have = 0
        total = have + int(resp.headers.get("Content-Length", 0))
        with open(dest, "ab" if have else "wb") as f:
            done, last = have, 0.0
            while chunk := resp.read(1 << 16):
                f.write(chunk)
                done += len(chunk)
                if time.time() - last > 10:
                    print(f"[prefetch] chroma model: {done / 1e6:.1f} / {total / 1e6:.1f} MB", flush=True)
                    last = time.time()


def chroma_model():
    if (CHROMA_DIR / "onnx" / "model.onnx").exists():
        return
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    archive = CHROMA_DIR / "onnx.tar.gz"
    if not (archive.exists() and sha256(archive) == CHROMA_SHA256):
        retry("chroma model", lambda: download_resumable(CHROMA_URL, archive))
        if sha256(archive) != CHROMA_SHA256:
            archive.unlink()
            sys.exit("[prefetch] chroma model: checksum mismatch, download corrupted - run the build again")
    with tarfile.open(archive, "r:gz") as tar:
        tar.extractall(path=CHROMA_DIR, filter="data")
    print("[prefetch] chroma model ready", flush=True)


# 2. Cross-encoder reranker (Hugging Face; resumes partial files by itself). Only the files
#    sentence-transformers loads - the repo also holds ONNX/OpenVINO copies that are never used.
def cross_encoder():
    from huggingface_hub import snapshot_download

    retry("cross-encoder", lambda: snapshot_download(
        "cross-encoder/ms-marco-MiniLM-L-6-v2",
        allow_patterns=["*.json", "*.txt", "model.safetensors"]))
    print("[prefetch] cross-encoder ready", flush=True)


# 3. tiktoken encoding for llm_guard's TokenLimit scanner (cached in TIKTOKEN_CACHE_DIR).
def tiktoken_encoding():
    import tiktoken

    retry("tiktoken", lambda: tiktoken.get_encoding("cl100k_base"))
    print("[prefetch] tiktoken ready", flush=True)


if __name__ == "__main__":
    os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "120")
    chroma_model()
    cross_encoder()
    tiktoken_encoding()
    print("[prefetch] done", flush=True)
