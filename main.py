import argparse
import heapq
import http.server
import os
import subprocess
import tempfile
import threading
from urllib.parse import unquote, urlparse

from PIL import Image
from playwright.sync_api import sync_playwright
from tqdm import tqdm


class FrameSink:
    def __init__(self, total, proc):
        self.total = total
        self.proc = proc
        self.heap = []
        self.next_frame = 0
        self.cv = threading.Condition()

    def add(self, pos, data):
        with self.cv:
            heapq.heappush(self.heap, (pos, data))
            self.cv.notify_all()

    def consume(self):
        with tqdm(total=self.total) as pbar:
            while True:
                with self.cv:
                    while self.next_frame < self.total and (
                        not self.heap or self.heap[0][0] != self.next_frame
                    ):
                        self.cv.wait()
                    if self.next_frame >= self.total:
                        break
                    self.next_frame += 1
                    data = heapq.heappop(self.heap)[1]
                self.proc.stdin.write(data)
                pbar.update(1)
        self.proc.stdin.close()
        self.proc.wait()


class PostHandler(http.server.SimpleHTTPRequestHandler):
    save_dir: str | None = None
    sink: FrameSink | None = None

    def translate_path(self, path: str) -> str:
        decoded = unquote(urlparse(path).path)
        if decoded == "/":
            return super().translate_path(path)
        return os.path.abspath(decoded)

    def do_POST(self):
        if self.path != "/save_frame":
            self.send_response(404)
            self.end_headers()
            return

        assert self.save_dir is not None

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)

        if PostHandler.sink is not None:
            name = self.headers.get("X-Frame-Name", "frame_00000.bytes")
            pos = int(name.split("_")[1].split(".")[0])
            PostHandler.sink.add(pos, body)
        else:
            name = self.headers.get("X-Frame-Name", "frame_00000.png")
            with open(os.path.join(self.save_dir, name), "wb") as f:
                f.write(body)

        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        pass


def render_worker(start, last, fps, step, port, cdp_port, init_args):
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{cdp_port}")
        context = browser.new_context()
        page = context.new_page()

        page.goto(f"http://127.0.0.1:{port}/")
        page.add_script_tag(path="node_modules/pixi.js/dist/pixi.js")
        page.add_script_tag(
            path="node_modules/@esotericsoftware/spine-pixi-v8/dist/iife/spine-pixi-v8.js"
        )
        page.add_script_tag(path="core.js")

        page.evaluate("args => init_spine(args)", init_args)
        page.evaluate(
            "([start, last, fps, step]) => render_frames(start, last, fps, step)",
            [start, last, fps, step],
        )
        context.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--atlas", required=True)
    ap.add_argument("--anim", required=True)
    ap.add_argument("--format", required=True, choices=["png", "webm"])
    ap.add_argument("--output", required=True)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--scale", type=float, default=1)
    ap.add_argument("--size")
    ap.add_argument("--offset", default="0,0")
    ap.add_argument("--port", type=int, default=8123)
    ap.add_argument("--cdp-port", type=int, default=9333)
    ap.add_argument("--parallel", type=int, default=4)
    args = ap.parse_args()

    w = h = None
    if args.size:
        w, h = map(int, args.size.split("x"))
    x, y = map(float, args.offset.split(","))

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", args.port), PostHandler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="chromium",
            args=[
                "--use-gl=angle",
                "--enable-features=Vulkan,VulkanFromANGLE",
                "--ignore-gpu-blocklist",
                f"--remote-debugging-port={args.cdp_port}",
            ],
        )
        page = browser.new_page()
        page.goto(f"http://127.0.0.1:{args.port}/")
        page.add_script_tag(path="node_modules/pixi.js/dist/pixi.js")
        page.add_script_tag(
            path="node_modules/@esotericsoftware/spine-pixi-v8/dist/iife/spine-pixi-v8.js"
        )
        page.add_script_tag(path="core.js")

        url = lambda p: (
            f"http://127.0.0.1:{args.port}" + os.path.abspath(os.path.expanduser(p))
        )

        info = page.evaluate(
            "args => init_spine(args)",
            {
                "skel_data": url(args.data),
                "skel_atlas": url(args.atlas),
                "anim": args.anim,
                "width": w,
                "height": h,
                "offset_x": x,
                "offset_y": y,
                "scale": args.scale,
            },
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            PostHandler.save_dir = tmpdir

            if args.format == "png":
                page.evaluate(
                    "([start, last, fps, step]) => render_frames(start, last, fps, step)",
                    [0, 1, args.fps, 1],
                )
                raw_path = os.path.join(tmpdir, "frame_00000.bytes")
                with open(raw_path, "rb") as f:
                    raw = f.read()
                img = Image.frombytes(
                    "RGBA", (int(info["width"]), int(info["height"])), raw
                )
                img.save(args.output, "PNG")
            else:
                ffmpeg = subprocess.Popen(
                    [
                        "ffmpeg",
                        "-y",
                        "-f",
                        "rawvideo",
                        "-pix_fmt",
                        "rgba",
                        "-s",
                        f"{int(info['width'])}x{int(info['height'])}",
                        "-r",
                        str(args.fps),
                        "-i",
                        "pipe:0",
                        "-c:v",
                        "libvpx-vp9",
                        "-pix_fmt",
                        "yuva420p",
                        "-row-mt",
                        "1",
                        "-deadline",
                        "realtime",
                        "-cpu-used",
                        "5",
                        args.output,
                    ],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

                total = max(int(info["duration"] * args.fps), 1)
                sink = FrameSink(total, ffmpeg)
                PostHandler.sink = sink

                consume_thread = threading.Thread(target=sink.consume)
                consume_thread.start()

                init_args = {
                    "skel_data": url(args.data),
                    "skel_atlas": url(args.atlas),
                    "anim": args.anim,
                    "width": int(info["width"]),
                    "height": int(info["height"]),
                    "offset_x": x,
                    "offset_y": y,
                    "scale": args.scale,
                }

                workers = []
                for start in range(args.parallel):
                    last = (total - start + args.parallel - 1) // args.parallel
                    if last <= 0:
                        continue

                    t = threading.Thread(
                        target=render_worker,
                        args=(
                            start,
                            last,
                            args.fps,
                            args.parallel,
                            args.port,
                            args.cdp_port,
                            init_args,
                        ),
                    )
                    t.start()
                    workers.append(t)

                for t in workers:
                    t.join()

                consume_thread.join()
                PostHandler.sink = None

        browser.close()


if __name__ == "__main__":
    main()
