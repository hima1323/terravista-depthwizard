"""Export a ViT student from train_distill.py (or RS3DAda itself) to ONNX for CPU inference, then check it.

The exported graph takes a normalised batch (N x 3 x P x P, P = the model's tile side, 518 for ViT) and returns
(height N x P x P in metres, land-cover logits N x 8 x P x P), the same as one predict() tile; N = 4 is the 4-flip TTA
batch. The check compares ONNX Runtime with PyTorch on the same input and times one TTA batch on the CPU.
MambaVision students cannot be exported: their Mamba layers are a custom CUDA kernel.

  python export_onnx.py pretrain/student_vits.pth            -> pretrain/student_vits.onnx
"""
import argparse, os, time

import numpy as np
import torch

import infer_height


class Tile(torch.nn.Module):
    def __init__(self, model):
        super().__init__()
        self.model = model

    def forward(self, x):
        o = self.model(x)
        return o['regression'][:, 0], o['segmentation']


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('weights')
    p.add_argument('--out', help='default: the weights path with .onnx')
    args = p.parse_args()
    out = args.out or os.path.splitext(args.weights)[0] + '.onnx'

    model, _, _ = infer_height.load_model(args.weights)
    if not hasattr(model, 'pretrained'):
        raise SystemExit('only DINOv2 (ViT) models export to ONNX; MambaVision runs on CUDA only')
    model = model.cpu().float().eval()
    P = model.patch_size
    x = torch.randn(4, 3, P, P)
    with torch.no_grad():   # reference first: exporting leaves the traced model in a state that no longer matches
        ref_h, ref_s = (t.numpy() for t in Tile(model)(x))
    torch.onnx.export(Tile(model), (x,), out, input_names=['image'], output_names=['height', 'landcover'],
                      dynamic_axes={'image': {0: 'n'}, 'height': {0: 'n'}, 'landcover': {0: 'n'}}, opset_version=17, dynamo=False)

    import onnxruntime as ort
    sess = ort.InferenceSession(out, providers=['CPUExecutionProvider'])
    sess.run(None, {'image': x.numpy()})                         # warm-up
    t0 = time.time()
    got_h, got_s = sess.run(None, {'image': x.numpy()})
    dt = time.time() - t0
    err_h, err_s = float(np.abs(got_h - ref_h).max()), float(np.abs(got_s - ref_s).max())
    print(f'{out}: {os.path.getsize(out) / 2**20:.0f} MB, opset 17, input n x 3 x {P} x {P}')
    print(f'ONNX Runtime vs PyTorch, max |diff|: height {err_h:.2e} m, land-cover logits {err_s:.2e}')
    print(f'CPU time for one 4-flip TTA tile batch: {dt:.2f} s')
    assert err_h < 1e-2 and err_s < 1e-2, 'ONNX output differs from PyTorch'


if __name__ == '__main__':
    main()
