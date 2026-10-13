import argparse
import threading
import http.server
import os
from playwright.sync_api import sync_playwright
import tempfile
from tqdm import tqdm
import subprocess
from typing import Optional
import shutil

class PostHandler(http.server.SimpleHTTPRequestHandler):
    save_dir: Optional[str] = None

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
    ap.add_argument('--format', required=True)
    ap.add_argument('--output', required=True)
    ap.add_argument('--fps', type=int, default=30)
    ap.add_argument('--scale', type=float, default=1)
    ap.add_argument('--size')
    ap.add_argument('--offset', default='0,0')
    args = ap.parse_args()

    if args.size is not None:
        w, h = args.size.split('x')
        w, h = int(w), int(h)
    else:
        w, h = None, None

    x, y = args.offset.split(',')
    x, y = float(x), float(y)

    httpd = http.server.ThreadingHTTPServer(('127.0.0.1', 8123), PostHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel='chromium',
            args=[
                '--use-gl=angle',
                '--enable-features=Vulkan,VulkanFromANGLE',
                '--ignore-gpu-blocklist',
                '--js-flags=--expose-gc'
            ]
        )
        page = browser.new_page()
        page.goto('http://127.0.0.1:8123/')
        page.add_script_tag(path='node_modules/pixi.js/dist/pixi.js')
        page.add_script_tag(path='node_modules/@esotericsoftware/spine-pixi-v8/dist/iife/spine-pixi-v8.js')
        page.add_script_tag(path='core.js')
        
        info = page.evaluate('args => init_spine(args)', {
            'skel_data': os.path.normpath(args.data),
            'skel_atlas': os.path.normpath(args.atlas),
            'anim': args.anim,
            'width': w,
            'height': h,
            'offset_x': x,
            'offset_y': y,
            'scale': args.scale
        })

        if args.format == 'png':
            with tempfile.TemporaryDirectory() as dir:
                PostHandler.save_dir = dir
                page.evaluate(
                    '([count, fps, start]) => render_frames(count, fps, start)',
                    [1, args.fps, 0]
                )
                shutil.copy(os.path.join(dir, 'frame_00000.png'), args.output)
                
        elif args.format == 'webm':
            with tempfile.TemporaryDirectory() as dir:
                PostHandler.save_dir = dir
                
                count = max(int(info['duration'] * args.fps), 1)
                rest = count
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
                    '-i', os.path.join(dir, 'frame_%05d.png'),
                    '-c:v', 'libvpx-vp9',
                    '-pix_fmt', 'yuv420p',
                    args.output
                ], check=True)

        browser.close()

if __name__ == '__main__':
    main()
