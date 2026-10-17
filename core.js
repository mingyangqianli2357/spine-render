"use strict";
const init_spine = async (args) => {
    PIXI.Assets.add({ alias: "skel-data", src: args.skel_data });
    PIXI.Assets.add({ alias: "skel-atlas", src: args.skel_atlas });
    await PIXI.Assets.load(['skel-data', 'skel-atlas']);
    const sp = spine.Spine.from({ skeleton: 'skel-data', atlas: 'skel-atlas' });
    sp.state.setAnimation(0, args.anim, false);
    sp.update(0);
    const basebounds = sp.getBounds();
    const width = args.width || Math.ceil(basebounds.width);
    const height = args.height || Math.ceil(basebounds.height);
    const app = new PIXI.Application();
    await app.init({
        width: width,
        height: height,
        backgroundAlpha: 0,
        preference: 'webgl'
    });
    app.ticker.stop();
    sp.autoUpdate = false;
    sp.scale.set(args.scale);
    const bounds = sp.getBounds();
    sp.x = width / 2 - (bounds.x + bounds.width / 2) + args.offset_x;
    sp.y = height / 2 - (bounds.y + bounds.height / 2) + args.offset_y;
    app.stage.addChild(sp);
    const render_frames = async (count, fps, start) => {
        const dt = 1 / fps;
        const frame = new PIXI.Rectangle(0, 0, width, height);
        for (let i = 0; i < count; ++i) {
            app.renderer.render(app.stage);
            const canvas = app.renderer.extract.canvas({ target: app.stage, frame });
            const blob = await new Promise((resolve, reject) => canvas.toBlob(b => {
                if (b)
                    resolve(b);
                else
                    reject('toBlob failed');
            }));
            const filename = 'frame_' + String(start + i).padStart(5, '0') + '.png';
            await fetch('/save_frame', {
                method: 'POST',
                headers: { 'X-Frame-Name': filename },
                body: blob
            });
            canvas.width = 0;
            canvas.height = 0;
            sp.update(dt);
        }
    };
    window.init_spine = init_spine;
    window.render_frames = render_frames;
    return {
        duration: sp.skeleton.data.findAnimation(args.anim).duration,
        width: width,
        height: height
    };
};
