"""Distil RS3DAda (DINOv2 ViT-L + DPT, the teacher) into a smaller student with the same two heads (height in metres,
8 land-cover classes): DINOv2 ViT-S / ViT-B (fast on CPU, exports to ONNX) or NVIDIA MambaVision (GPU only).

The student learns the teacher's outputs on random crops of unlabelled images: smooth-L1 on height, KL divergence
(temperature 2) on land cover. A student copies the teacher, including its known faults (tall objects ~15-18 m too
low); --gt_weight adds SynRS3D's own height labels (gt_nDSM next to opt/) where they exist. Needs a CUDA GPU.

Never put benchmark test images (GAMUS test, OGC ATL/ARG test, the Indian scenes) in --images.

  python train_distill.py --images /data/SynRS3D --student vits --out pretrain/student_vits.pth
  python train_distill.py --images /data/SynRS3D --student nvidia/MambaVision-T-1K --out pretrain/student_mambavision_t.pth
Then evaluate exactly like the teacher (docs/GPU_TRAINING.md, section 4):
  DW_WEIGHTS=pretrain/student_vits.pth python demo/gamus_benchmark.py && DW_WEIGHTS=pretrain/student_vits.pth python demo/gamus_v2.py
"""
import argparse, glob, json, math, os, random, time

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

import infer_height
from models.dpt import make_model

MEAN = torch.tensor([123.675, 116.28, 103.53]).view(1, 3, 1, 1)   # infer_height.predict's normalisation (0-255 scale)
STD = torch.tensor([58.395, 57.12, 57.375]).view(1, 3, 1, 1)


class Crops(torch.utils.data.Dataset):
    """Random (train) or centre (val) square crops of RGB images, with random flips / 90° turns when training.
    Returns uint8 CHW image and the matching gt_nDSM crop (NaN where there is none)."""

    def __init__(self, files, crop, train):
        self.files, self.crop, self.train = files, crop, train

    def __len__(self):
        return len(self.files)

    def __getitem__(self, i):
        f = self.files[i]
        img = np.asarray(Image.open(f).convert('RGB'))
        gt_f = f.replace(os.sep + 'opt' + os.sep, os.sep + 'gt_nDSM' + os.sep)
        gt = np.asarray(Image.open(gt_f), np.float32) if gt_f != f and os.path.exists(gt_f) else np.full(img.shape[:2], np.nan, np.float32)
        c, (h, w) = self.crop, img.shape[:2]
        if h < c or w < c:   # small tiles: reflect-pad up to the crop (gt padded with NaN: no label there)
            ph, pw = max(0, c - h), max(0, c - w)
            img = np.pad(img, ((0, ph), (0, pw), (0, 0)), mode='reflect')
            gt = np.pad(gt, ((0, ph), (0, pw)), constant_values=np.nan)
            h, w = img.shape[:2]
        y, x = (random.randint(0, h - c), random.randint(0, w - c)) if self.train else ((h - c) // 2, (w - c) // 2)
        img, gt = img[y:y + c, x:x + c], gt[y:y + c, x:x + c]
        if self.train:
            k = random.randint(0, 3)
            img, gt = np.rot90(img, k), np.rot90(gt, k)
            if random.random() < 0.5:
                img, gt = img[:, ::-1], gt[:, ::-1]
        return torch.from_numpy(np.ascontiguousarray(img)).permute(2, 0, 1), torch.from_numpy(np.ascontiguousarray(gt))


def normalise(x):
    return (x.float() - MEAN.to(x.device)) / STD.to(x.device)


@torch.no_grad()
def teach(teacher, x):
    """Teacher outputs on a normalised batch; its ViT needs sides that are multiples of 14, so pad and crop back."""
    h, w = x.shape[-2:]
    ph, pw = (-h) % 14, (-w) % 14
    xp = F.pad(x, (0, pw, 0, ph), mode='reflect') if ph or pw else x
    with torch.autocast('cuda', dtype=torch.float16):
        o = teacher(xp)
    return o['regression'][:, 0, :h, :w].float(), o['segmentation'][:, :, :h, :w].float()


def losses(out, t_h, t_seg, gt, args):
    s_h, s_seg = out['regression'][:, 0].float(), out['segmentation'].float()
    l_h = F.smooth_l1_loss(s_h, t_h)
    T = args.temperature
    l_seg = F.kl_div(F.log_softmax(s_seg / T, 1), F.softmax(t_seg / T, 1), reduction='none').sum(1).mean() * T * T
    m = torch.isfinite(gt)
    l_gt = F.smooth_l1_loss(s_h[m], gt[m]) if args.gt_weight and m.any() else s_h.new_zeros(())
    return l_h + args.seg_weight * l_seg + args.gt_weight * l_gt, {'height': l_h.item(), 'seg': l_seg.item(), 'gt': l_gt.item()}


def lr_at(step, args):   # linear warm-up, then cosine to 0
    if step < args.warmup:
        return (step + 1) / args.warmup
    return 0.5 * (1 + math.cos(math.pi * (step - args.warmup) / max(1, args.steps - args.warmup)))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--images', nargs='+', required=True, help='folders searched with --pattern')
    p.add_argument('--pattern', default='**/opt/*.tif', help='glob under each folder (SynRS3D / RS3DAda layout: <set>/opt/<id>.tif)')
    p.add_argument('--student', default='vits', help="vits | vitb | a MambaVision Hugging Face id, e.g. nvidia/MambaVision-T-1K")
    p.add_argument('--teacher', default=infer_height.WEIGHTS)
    p.add_argument('--out', required=True)
    p.add_argument('--steps', type=int, default=20000)
    p.add_argument('--batch', type=int, default=8)
    p.add_argument('--lr', type=float, default=1e-4, help='heads')
    p.add_argument('--enc_lr', type=float, default=1e-5, help='pretrained encoder')
    p.add_argument('--warmup', type=int, default=500)
    p.add_argument('--seg_weight', type=float, default=0.5)
    p.add_argument('--temperature', type=float, default=2.0)
    p.add_argument('--gt_weight', type=float, default=0.0, help='> 0: also fit gt_nDSM labels where they exist (SynRS3D)')
    p.add_argument('--workers', type=int, default=4)
    p.add_argument('--save_every', type=int, default=1000)
    p.add_argument('--val_every', type=int, default=1000)
    args = p.parse_args()
    assert torch.cuda.is_available(), 'distillation needs a CUDA GPU (Kaggle / Colab: enable the GPU accelerator)'
    random.seed(0), torch.manual_seed(0)

    files = sorted(f for d in args.images for f in glob.glob(os.path.join(d, args.pattern), recursive=True))
    assert files, f'no images match {args.pattern} under {args.images}'
    random.Random(0).shuffle(files)
    n_val = max(16, len(files) // 50)
    val, train = files[:n_val], files[n_val:]
    print(f'{len(train)} training / {len(val)} validation images', flush=True)

    student, crop = make_model(args.student, pretrained=True)
    teacher, _, _ = infer_height.load_model(args.teacher, fp16=False)
    student.cuda().train()
    teacher.cuda().eval().requires_grad_(False)
    enc = student.pretrained if hasattr(student, 'pretrained') else student.backbone
    enc_ids = {id(q) for q in enc.parameters()}
    opt = torch.optim.AdamW([{'params': list(enc.parameters()), 'lr': args.enc_lr},
                             {'params': [q for q in student.parameters() if id(q) not in enc_ids], 'lr': args.lr}], weight_decay=1e-4)
    base = [g['lr'] for g in opt.param_groups]
    scaler = torch.amp.GradScaler('cuda')
    step = 0
    if os.path.exists(args.out + '.resume'):   # Kaggle sessions end after 9-12 h: carry on where the last one stopped
        r = torch.load(args.out + '.resume', map_location='cpu', weights_only=False)
        student.load_state_dict(r['state_dict']), opt.load_state_dict(r['opt']), scaler.load_state_dict(r['scaler'])
        step = r['step']
        print(f'resumed at step {step}', flush=True)

    loader = torch.utils.data.DataLoader(Crops(train, crop, True), args.batch, shuffle=True, num_workers=args.workers,
                                         drop_last=True, pin_memory=True, persistent_workers=args.workers > 0)
    val_loader = torch.utils.data.DataLoader(Crops(val, crop, False), args.batch, num_workers=args.workers)
    log = open(args.out + '.log.jsonl', 'a')

    def save(final=False):
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        meta = {'encoder': args.student, 'patch_size': crop, 'step': step, 'teacher': os.path.basename(args.teacher),
                'gt_weight': args.gt_weight}
        torch.save(dict(meta, state_dict=student.state_dict()), args.out)   # what infer_height.load_model reads
        if not final:
            torch.save(dict(meta, state_dict=student.state_dict(), opt=opt.state_dict(), scaler=scaler.state_dict()), args.out + '.resume')

    @torch.no_grad()
    def validate():
        student.eval()
        err, n = 0.0, 0
        for x, _ in val_loader:
            x = normalise(x.cuda(non_blocking=True))
            t_h, _ = teach(teacher, x)
            with torch.autocast('cuda', dtype=torch.float16):
                s_h = student(x)['regression'][:, 0].float()
            err += (s_h - t_h).abs().mean().item() * len(x)
            n += len(x)
        student.train()
        return err / n

    t0 = time.time()
    while step < args.steps:
        for x, gt in loader:
            if step >= args.steps:
                break
            for g, b in zip(opt.param_groups, base):
                g['lr'] = b * lr_at(step, args)
            x, gt = normalise(x.cuda(non_blocking=True)), gt.cuda(non_blocking=True)
            t_h, t_seg = teach(teacher, x)
            with torch.autocast('cuda', dtype=torch.float16):
                out = student(x)
            loss, parts = losses(out, t_h, t_seg, gt, args)
            opt.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.unscale_(opt)
            torch.nn.utils.clip_grad_norm_(student.parameters(), 1.0)
            scaler.step(opt), scaler.update()
            step += 1
            if step % 50 == 0:
                rec = dict(step=step, loss=loss.item(), **parts, lr=opt.param_groups[1]['lr'], min=(time.time() - t0) / 60)
                print(json.dumps(rec), flush=True)
                log.write(json.dumps(rec) + '\n'), log.flush()
            if step % args.val_every == 0 or step == args.steps:
                v = validate()
                print(json.dumps({'step': step, 'val_mae_vs_teacher_m': v}), flush=True)
                log.write(json.dumps({'step': step, 'val_mae_vs_teacher_m': v}) + '\n'), log.flush()
            if step % args.save_every == 0:
                save()
    save(final=True)
    print(f'saved {args.out} ({step} steps, {(time.time() - t0) / 3600:.1f} h)', flush=True)


if __name__ == '__main__':
    main()
