"""Extract selected members from a huge remote .zip using HTTP range requests (no full download).

usage: python demo/remote_zip.py <url> <out_dir> [pattern ...]   (no pattern = list members)
"""
import fnmatch, io, os, sys, urllib.request, zipfile


class HttpFile(io.RawIOBase):
    """Seekable read-only file over HTTP Range requests."""

    def __init__(self, url):
        self.url, self.pos = url, 0
        req = urllib.request.Request(url, method='HEAD')
        self.size = int(urllib.request.urlopen(req, timeout=60).headers['Content-Length'])

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, off, whence=0):
        self.pos = {0: off, 1: self.pos + off, 2: self.size + off}[whence]
        return self.pos

    def readinto(self, b):
        n = min(len(b), self.size - self.pos)
        if n <= 0:
            return 0
        for attempt in range(5):  # retry flaky connections
            try:
                req = urllib.request.Request(self.url, headers={'Range': f'bytes={self.pos}-{self.pos + n - 1}'})
                data = urllib.request.urlopen(req, timeout=120).read()
                break
            except OSError:
                if attempt == 4:
                    raise
        b[:len(data)] = data
        self.pos += len(data)
        return len(data)


def open_zip(url):
    return zipfile.ZipFile(io.BufferedReader(HttpFile(url), buffer_size=1 << 20))


def main(workers=4):
    url, out = sys.argv[1], sys.argv[2]
    patterns = []
    for p in sys.argv[3:]:  # "@list.txt" = read patterns from a file, one per line
        patterns += open(p[1:]).read().split() if p.startswith('@') else [p]
    names = open_zip(url).namelist()
    if not patterns:
        print('\n'.join(names))
        return
    todo = [n for n in names if any(fnmatch.fnmatch(n, p) for p in patterns)
            and not os.path.exists(os.path.join(out, n))]
    done = [0]

    def work(chunk):  # each thread gets its own connection + zip handle
        zf = open_zip(url)
        for n in chunk:
            zf.extract(n, out)
            done[0] += 1
            print(f'[{done[0]}/{len(todo)}] {n}', flush=True)

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(workers) as ex:
        list(ex.map(work, [todo[i::workers] for i in range(workers)]))


if __name__ == '__main__':
    main()
