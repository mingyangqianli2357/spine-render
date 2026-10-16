declare const PIXI: typeof import('pixi.js');
declare const spine: typeof import('@esotericsoftware/spine-pixi-v8');

interface Init_Args {
  skel_data: string
  skel_atlas: string
  anim: string
  width?: number
  height?: number
  offset_x: number
  offset_y: number
  scale: number
}

interface Init_Res {
  duration: number
  width: number
  height: number
}

const init_spine = async (args: Init_Args): Promise<Init_Res> => {
  PIXI.Assets.add({ alias: "skel-data", src: args.skel_data })
  PIXI.Assets.add({ alias: "skel-atlas", src: args.skel_atlas })
  await PIXI.Assets.load(['skel-data', 'skel-atlas'])

  const sp = spine.Spine.from({ skeleton: 'skel-data', atlas: 'skel-atlas' })

  sp.state.setAnimation(0, args.anim, false)
  sp.update(0)
  sp.scale.set(args.scale)

  const bounds = sp.getBounds()
  const app = new PIXI.Application()
  await app.init({
    width: args.width || Math.ceil(bounds.width),
    height: args.height || Math.ceil(bounds.height),
    backgroundAlpha: 0,
    preference: 'webgl'
  })
  app.ticker.stop()
  sp.autoUpdate = false;

  sp.x = (args.width || Math.ceil(bounds.width)) / 2 - (bounds.x + bounds.width / 2) + args.offset_x
  sp.y = (args.height || Math.ceil(bounds.height)) / 2 - (bounds.y + bounds.height / 2) + args.offset_y
  app.stage.addChild(sp)

  const render_frames = async (count: number, fps: number, start: number) => {
    const dt = 1 / fps
    for (let i = 0; i < count; ++i) {
      app.renderer.render(app.stage)

      const canvas = app.renderer.extract.canvas(app.stage) as HTMLCanvasElement

      const blob = await new Promise<Blob>((resolve, reject) =>
        canvas.toBlob(b => {
          if (b)
            resolve(b)
          else
            reject('toBlob failed')
        })
      )

      const filename = 'frame_' + String(start + i).padStart(5, '0') + '.png'
      await fetch('/save_frame', {
        method: 'POST',
        headers: {'X-Frame-Name': filename},
        body: blob
      })

      canvas.width = 0
      canvas.height = 0
      sp.update(dt)
    }
  }

  ;(window as any).init_spine = init_spine
  ;(window as any).render_frames = render_frames

  return {
    duration: sp.skeleton.data.findAnimation(args.anim)!.duration,
    width: args.width || Math.ceil(bounds.width),
    height: args.height || Math.ceil(bounds.height)
  }
}
