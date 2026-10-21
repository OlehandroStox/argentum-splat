"""Download the pinned official Windows CUDA wheel with resumable ranges."""
import argparse
import concurrent.futures
import hashlib
import html
import os
from pathlib import Path
import re
import sys
import time
import urllib.parse
import urllib.request

TORCH_VERSION = "2.9.1"
CHUNK = 16 * 1024 * 1024


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download(cache):
    tag = "cp%d%d" % sys.version_info[:2]
    filename = "torch-%s+cu128-%s-%s-win_amd64.whl" % (TORCH_VERSION, tag, tag)
    index_url = "https://download.pytorch.org/whl/cu128/torch/"
    with urllib.request.urlopen(index_url, timeout=60) as response:
        index = response.read().decode("utf-8")
    selected = None
    for match in re.finditer(r'href="([^"]+)"', index):
        link = html.unescape(match.group(1))
        if urllib.parse.unquote(urllib.parse.urlsplit(link).path).endswith("/" + filename):
            selected = urllib.parse.urljoin(index_url, link)
            break
    if selected is None:
        raise RuntimeError("Official CUDA wheel is unavailable for " + tag)
    parsed = urllib.parse.urlsplit(selected)
    expected = urllib.parse.parse_qs(parsed.fragment).get("sha256", [""])[0]
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise RuntimeError("Official wheel index did not provide a SHA-256.")
    # The first-party CloudFront endpoint handles long streaming requests more
    # reliably than R2 on some Windows networks. Verify the official wheel hash.
    url = urllib.parse.urlunsplit(("https", "download.pytorch.org", parsed.path, "", ""))
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / filename
    if target.is_file() and sha256(target) == expected:
        print(str(target), flush=True)
        return target
    with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=60) as response:
        total = int(response.headers["Content-Length"])
    parts = cache / (filename + ".parts")
    parts.mkdir(exist_ok=True)
    count = (total + CHUNK - 1) // CHUNK

    def fetch(number):
        start = number * CHUNK
        end = min(total, start + CHUNK) - 1
        length = end - start + 1
        part = parts / ("%05d.bin" % number)
        if part.is_file() and part.stat().st_size == length:
            return length
        temporary = part.with_suffix(".tmp")
        last_error = None
        for attempt in range(5):
            try:
                request = urllib.request.Request(url, headers={"Range": "bytes=%d-%d" % (start, end)})
                with urllib.request.urlopen(request, timeout=120) as response:
                    if response.status != 206:
                        raise RuntimeError("Server did not honor a byte-range request.")
                    content_range = response.headers.get("Content-Range", "")
                    if not content_range.startswith("bytes %d-%d/" % (start, end)):
                        raise RuntimeError("Unexpected download byte range.")
                    with temporary.open("wb") as output:
                        while True:
                            block = response.read(1024 * 1024)
                            if not block:
                                break
                            output.write(block)
                if temporary.stat().st_size != length:
                    raise RuntimeError("Incomplete download chunk.")
                temporary.replace(part)
                return length
            except Exception as exc:
                last_error = exc
                time.sleep(min(2 ** attempt, 8))
        raise RuntimeError("Could not download chunk %d: %s" % (number, last_error))

    completed = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(fetch, index) for index in range(count)]
        for future in concurrent.futures.as_completed(futures):
            completed += future.result()
            print("PyTorch download: %.0f / %.0f MiB" % (completed / 1048576, total / 1048576), flush=True)
    temporary = target.with_suffix(".whl.tmp")
    with temporary.open("wb") as output:
        for number in range(count):
            with (parts / ("%05d.bin" % number)).open("rb") as source:
                while True:
                    block = source.read(8 * 1024 * 1024)
                    if not block:
                        break
                    output.write(block)
    if sha256(temporary) != expected:
        # Length alone cannot authenticate resumable chunks. Discard this
        # download's parts so a subsequent Install can recover from corruption.
        for number in range(count):
            (parts / ("%05d.bin" % number)).unlink(missing_ok=True)
        temporary.unlink(missing_ok=True)
        raise RuntimeError("PyTorch SHA-256 verification failed; no code was installed.")
    temporary.replace(target)
    for number in range(count):
        (parts / ("%05d.bin" % number)).unlink()
    parts.rmdir()
    print(str(target), flush=True)
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-dir", required=True)
    args = parser.parse_args()
    download(Path(args.cache_dir).resolve())
