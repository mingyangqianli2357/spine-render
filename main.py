import argparse
import threading
import http.server
import os
from playwright.sync_api import sync_playwright
import tempfile
from tqdm import tqdm
import subprocess
import shutil
from urllib.parse import unquote, urlparse

class PostHandler(http.server.SimpleHTTPRequestHandler):
    save_dir: str | None = None

    def translate_path(self, path: str) -> str:
        decoded = unquote(urlparse(path).path)
        if decoded == '/':
            return super().translate_path(path)
        return os.path.abspath(decoded)

    def do_POST(self):
        if self.path != '/save_frame':
            self.send_response(404)
            self.end_headers()
            return

        assert self.save_dir is not None
        
        length = int(self.headers.get('Content-Length', 0))
        name = self.headers.get('X-Frame-Name', 'frame_00000.png')

        with open(os.path.join(self.save_dir, name), 'wb') as f:
            f.write(self.rfile.read(length))

        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        pass

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True)
    ap.add_argument('--atlas', required=True)
    ap.add_argument('--anim', required=True)
    ap.add_argument('--format', required=True, choices=['png', 'webm'])
    ap.add_argument('--output', required=True)
    ap.add_argument('--fps', type=int, default=30)
    ap.add_argument('--scale', type=float, default=1)
    ap.add_argument('--size')
    ap.add_argument('--offset', default='0,0')
    ap.add_argument('--port', type=int, default=8123)
    args = ap.parse_args()

    w = h = None
    if args.size:
        w, h = map(int, args.size.split('x'))
    x, y = map(float, args.offset.split(','))

    httpd = http.server.ThreadingHTTPServer(('127.0.0.1', args.port), PostHandler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel='chromium',
            args=[
                '--use-gl=angle',
                '--enable-features=Vulkan,VulkanFromANGLE',
                '--ignore-gpu-blocklist'
            ]
        )
        page = browser.new_page()
        page.goto(f'http://127.0.0.1:{args.port}/')
        page.add_script_tag(path='node_modules/pixi.js/dist/pixi.js')
        page.add_script_tag(path='node_modules/@esotericsoftware/spine-pixi-v8/dist/iife/spine-pixi-v8.js')
        page.add_script_tag(path='core.js')

        url = lambda p: f'http://127.0.0.1:{args.port}' + os.path.abspath(os.path.expanduser(p))

        info = page.evaluate('args => init_spine(args)', {
            'skel_data': url(args.data),
            'skel_atlas': url(args.atlas),
            'anim': args.anim,
            'width': w,
            'height': h,
            'offset_x': x,
            'offset_y': y,
            'scale': args.scale
        })

        with tempfile.TemporaryDirectory() as tmpdir:
            PostHandler.save_dir = tmpdir
            if args.format == 'png':
                page.evaluate(
                    '([count, fps, start]) => render_frames(count, fps, start)',
                    [1, args.fps, 0]
                )
                shutil.copy(os.path.join(tmpdir, 'frame_00000.png'), args.output)
        
            else:
                rest = count = max(int(info['duration'] * args.fps), 1)
                start = 0
                pbar = tqdm(total=count)

                while rest > 0:
                    batch = min(rest, 10)
                    page.evaluate(
                        '([count, fps, start]) => render_frames(count, fps, start)',
                        [batch, args.fps, start]
                    )
                    start += batch
                    rest -= batch
                    pbar.update(batch)

                pbar.close()

                subprocess.run([
                    'ffmpeg', '-y',
                    '-framerate', str(args.fps),
                    '-i', os.path.join(tmpdir, 'frame_%05d.png'),
                    '-c:v', 'libvpx-vp9',
                    '-pix_fmt', 'yuva420p',
                    args.output
                ], check=True)
                
       
if __name__ == '__main__':
    main()
