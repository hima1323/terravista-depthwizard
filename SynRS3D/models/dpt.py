import argparse
import os
import torch
import torch.nn as nn
import torch.nn.functional as F
from huggingface_hub import PyTorchModelHubMixin
from typing import Optional, List, Dict

from models.blocks import FeatureFusionBlock, _make_scratch


def _make_fusion_block(features, use_bn, size = None):
    return FeatureFusionBlock(
        features,
        nn.ReLU(False),
        deconv=False,
        bn=use_bn,
        expand=False,
        align_corners=True,
        size=size,
    )


class DPTHead(nn.Module):
    def __init__(self, nclass, in_channels, features=256, use_bn=False, out_channels=[256, 512, 1024, 1024], use_clstoken=False, in_dims=None):
        """in_dims: channels of the 4 stages of a hierarchical encoder (strides 4, 8, 16, 32, e.g. MambaVision). Those are
        already a pyramid, so each is only projected (1x1) and not reassembled from ViT tokens."""
        super(DPTHead, self).__init__()
        
        self.nclass = nclass
        self.use_clstoken = use_clstoken
        self.hierarchical = in_dims is not None
        
        self.projects = nn.ModuleList([
            nn.Conv2d(
                in_channels=in_dims[i] if in_dims else in_channels,
                out_channels=out_channel,
                kernel_size=1,
                stride=1,
                padding=0,
            ) for i, out_channel in enumerate(out_channels)
        ])
        
        self.resize_layers = nn.ModuleList([nn.Identity()] * 4) if in_dims else nn.ModuleList([
            nn.ConvTranspose2d(
                in_channels=out_channels[0],
                out_channels=out_channels[0],
                kernel_size=4,
                stride=4,
                padding=0),
            nn.ConvTranspose2d(
                in_channels=out_channels[1],
                out_channels=out_channels[1],
                kernel_size=2,
                stride=2,
                padding=0),
            nn.Identity(),
            nn.Conv2d(
                in_channels=out_channels[3],
                out_channels=out_channels[3],
                kernel_size=3,
                stride=2,
                padding=1)
        ])
        
        if use_clstoken:
            self.readout_projects = nn.ModuleList()
            for _ in range(len(self.projects)):
                self.readout_projects.append(
                    nn.Sequential(
                        nn.Linear(2 * in_channels, in_channels),
                        nn.GELU()))
        
        self.scratch = _make_scratch(
            out_channels,
            features,
            groups=1,
            expand=False,
        )

        self.scratch.stem_transpose = None
        
        self.scratch.refinenet1 = _make_fusion_block(features, use_bn)
        self.scratch.refinenet2 = _make_fusion_block(features, use_bn)
        self.scratch.refinenet3 = _make_fusion_block(features, use_bn)
        self.scratch.refinenet4 = _make_fusion_block(features, use_bn)

        head_features_1 = features
        head_features_2 = 32
        
        if nclass > 1:
            self.scratch.output_conv = nn.Sequential(
                nn.Conv2d(head_features_1, head_features_1, kernel_size=3, stride=1, padding=1),
                nn.Conv2d(head_features_1, nclass, kernel_size=1, stride=1, padding=0),
            )
        else:
            self.scratch.output_conv1 = nn.Conv2d(head_features_1, head_features_1 // 2, kernel_size=3, stride=1, padding=1)
            
            self.scratch.output_conv2 = nn.Sequential(
                nn.Conv2d(head_features_1 // 2, head_features_2, kernel_size=3, stride=1, padding=1),
                nn.Conv2d(head_features_2, 1, kernel_size=1, stride=1, padding=0),
                nn.Identity(),
            )
            
    def forward(self, out_features, patch_h, patch_w, size=None):
        """size: output (h, w) of the height head; default the ViT input size patch * 14."""
        out = []
        for i, x in enumerate(out_features):
            if self.hierarchical:
                out.append(self.projects[i](x))
                continue
            if self.use_clstoken:
                x, cls_token = x[0], x[1]
                readout = cls_token.unsqueeze(1).expand_as(x)
                x = self.readout_projects[i](torch.cat((x, readout), -1))
            else:
                x = x[0]
            
            x = x.permute(0, 2, 1).reshape((x.shape[0], x.shape[-1], patch_h, patch_w))
            
            x = self.projects[i](x)
            x = self.resize_layers[i](x)
            
            out.append(x)
        
        layer_1, layer_2, layer_3, layer_4 = out
        
        layer_1_rn = self.scratch.layer1_rn(layer_1)
        layer_2_rn = self.scratch.layer2_rn(layer_2)
        layer_3_rn = self.scratch.layer3_rn(layer_3)
        layer_4_rn = self.scratch.layer4_rn(layer_4)
        
        path_4 = self.scratch.refinenet4(layer_4_rn, size=layer_3_rn.shape[2:])
        path_3 = self.scratch.refinenet3(path_4, layer_3_rn, size=layer_2_rn.shape[2:])
        path_2 = self.scratch.refinenet2(path_3, layer_2_rn, size=layer_1_rn.shape[2:])
        path_1 = self.scratch.refinenet1(path_2, layer_1_rn)
        
        if self.nclass > 1:
            out = self.scratch.output_conv(path_1)
        else:
            out = self.scratch.output_conv1(path_1)
            out = F.interpolate(out, size or (int(patch_h * 14), int(patch_w * 14)), mode="bilinear", align_corners=True)
            out = self.scratch.output_conv2(out)
        
        return out
        
        
class DPT_DINOv2(nn.Module):
    def __init__(self, encoder='vitl', head_configs: Optional[List[Dict]] = None, features=256, out_channels=[256, 512, 1024, 1024], use_clstoken=False, pretrained=True):
        super(DPT_DINOv2, self).__init__()
        
        assert encoder in ['vits', 'vitb', 'vitl']
        
        # DINOv2 code: a local copy if there is one (installer / torch hub cache), so the app also starts offline;
        # otherwise GitHub (downloaded once into the torch hub cache)
        local = [d for d in (os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'pretrain', 'dinov2'),
                             os.path.join(torch.hub.get_dir(), 'facebookresearch_dinov2_main')) if os.path.isfile(os.path.join(d, 'hubconf.py'))]
        if local:
            self.pretrained = torch.hub.load(local[0], 'dinov2_{:}14'.format(encoder), source='local', pretrained=pretrained)
        else:
            self.pretrained = torch.hub.load('facebookresearch/dinov2', 'dinov2_{:}14'.format(encoder), pretrained=pretrained)
        
        dim = self.pretrained.blocks[0].attn.qkv.in_features
        
        self.head_configs = head_configs or []
        self.heads = nn.ModuleDict()
        
        # Dynamically creating heads based on configurations
        for config in self.head_configs:
            task = config['name']
            use_bn = True
            nclass = config.get('nclass', None)
            head = DPTHead(nclass, dim, features, use_bn, out_channels, use_clstoken)
            self.heads[task] = head
        
    def forward(self, x):
        h, w = x.shape[-2:]
        
        features = self.pretrained.get_intermediate_layers(x, 4, return_class_token=True)
        
        patch_h, patch_w = h // 14, w // 14
        outputs = {}

        for task, head in self.heads.items():
            output = head(features, patch_h, patch_w)

            output = F.interpolate(output, size=(h, w), mode="bilinear", align_corners=True)
                
            outputs[task] = output
            
        return outputs

    

class DPT_MambaVision(nn.Module):
    """NVIDIA MambaVision (hybrid Mamba-Transformer, ImageNet weights from Hugging Face) as the encoder, with the same
    DPT heads as RS3DAda. Its Mamba mixer is a CUDA kernel (mamba_ssm): it runs on an NVIDIA GPU only, not on CPU or
    Apple MPS, and does not export to ONNX. Input sides must be multiples of 32."""

    def __init__(self, name='nvidia/MambaVision-T-1K', head_configs=None, features=128, use_bn=False):
        super().__init__()
        from transformers import AutoModel
        self.backbone = AutoModel.from_pretrained(name, trust_remote_code=True)
        dims = [self.backbone.config.dim * 2 ** i for i in range(4)]   # stage widths double: T 80-160-320-640
        self.heads = nn.ModuleDict({c['name']: DPTHead(c['nclass'], None, features, use_bn, dims, in_dims=dims)
                                    for c in head_configs or []})

    def forward(self, x):
        h, w = x.shape[-2:]
        _, feats = self.backbone(x)          # pooled output, 4 stage maps at strides 4/8/16/32
        return {task: F.interpolate(head(feats, None, None, size=(h, w)), size=(h, w), mode='bilinear', align_corners=True)
                for task, head in self.heads.items()}


HEADS = [{'name': 'regression', 'nclass': 1}, {'name': 'segmentation', 'nclass': 8}]   # RS3DAda: height + 8 land-cover classes
# DPT head sizes per DINOv2 encoder, as in Depth Anything V2; vitl is RS3DAda's
DINO_HEAD = {'vits': (64, [48, 96, 192, 384]), 'vitb': (128, [96, 192, 384, 768]), 'vitl': (256, [256, 512, 1024, 1024])}


def make_model(encoder, pretrained=True):
    """encoder: 'vits' / 'vitb' / 'vitl' (DINOv2 + DPT) or a MambaVision Hugging Face id ('nvidia/MambaVision-T-1K', ...).
    Returns (model, patch size): a ViT tile must be a multiple of 14 (518), MambaVision a multiple of 32 (512)."""
    if encoder in DINO_HEAD:
        features, out_channels = DINO_HEAD[encoder]
        return DPT_DINOv2(encoder, HEADS, features, out_channels, pretrained=pretrained), 518
    return DPT_MambaVision(encoder, HEADS), 512
