"""Anonymous, resumable public checkpoint downloads with SHA-256 verification."""
import concurrent.futures
import hashlib
from pathlib import Path
import time
import urllib.parse
import urllib.request

CHUNK = 16 * 1024 * 1024


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download(repo, revision, filename, target, expected_size, expected_hash):
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file() and target.stat().st_size == expected_size and sha256(target) == expected_hash:
        print("Verified " + filename, flush=True)
        return expected_hash
    url = "https://huggingface.co/%s/resolve/%s/%s" % (
        repo, revision, urllib.parse.quote(filename, safe="/")
    )
    parts = target.with_name(target.name + ".parts")
    parts.mkdir(exist_ok=True)
    count = (expected_size + CHUNK - 1) // CHUNK

    def fetch(number):
        start = number * CHUNK
        end = min(expected_size, start + CHUNK) - 1
        length = end - start + 1
        part = parts / ("%05d.bin" % number)
        if part.is_file() and part.stat().st_size == length:
            return length
        temporary = part.with_suffix(".tmp")
        last_type = None
        for attempt in range(5):
            try:
                # A unique query avoids stale proxy responses to differing Range
                # headers. No account token, cookie, or credential is used.
                request = urllib.request.Request(
                    url + "?download=true&range=%d-%d" % (start, end),
                    headers={"Range": "bytes=%d-%d" % (start, end)},
                )
                with urllib.request.urlopen(request, timeout=90) as response:
                    wanted = "bytes %d-%d/%d" % (start, end, expected_size)
                    if response.status != 206 or response.headers.get("Content-Range") != wanted:
                        raise RuntimeError("Server returned an unexpected byte range.")
                    with temporary.open("wb") as output:
                        for block in iter(lambda: response.read(1024 * 1024), b""):
                            output.write(block)
                if temporary.stat().st_size != length:
                    raise RuntimeError("Incomplete checkpoint chunk.")
                temporary.replace(part)
                return length
            except Exception as exc:
                last_type = type(exc).__name__
                time.sleep(min(2 ** attempt, 8))
        # Do not echo expiring signed redirect URLs into application logs.
        raise RuntimeError("Checkpoint download failed: %s, chunk %d (%s)." % (
            filename, number, last_type
        ))

    completed = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(fetch, index) for index in range(count)]
        for future in concurrent.futures.as_completed(futures):
            completed += future.result()
            print("%s: %.0f / %.0f MiB" % (
                filename, completed / 1048576, expected_size / 1048576
            ), flush=True)
    temporary = target.with_name(target.name + ".download")
    with temporary.open("wb") as output:
        for number in range(count):
            with (parts / ("%05d.bin" % number)).open("rb") as source:
                for block in iter(lambda: source.read(8 * 1024 * 1024), b""):
                    output.write(block)
    actual = sha256(temporary)
    if actual != expected_hash:
        # Invalid resumable chunks must not poison every subsequent retry.
        for number in range(count):
            (parts / ("%05d.bin" % number)).unlink()
        temporary.unlink()
        raise RuntimeError("Checkpoint SHA-256 verification failed: " + filename)
    temporary.replace(target)
    for number in range(count):
        (parts / ("%05d.bin" % number)).unlink()
        (parts / ("%05d.tmp" % number)).unlink(missing_ok=True)
    parts.rmdir()
    print("Verified " + filename, flush=True)
    return actual
