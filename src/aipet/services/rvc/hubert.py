import torch
import torch.nn as nn
import torch.nn.functional as F

class FeatureExtractor(nn.Module):
    def __init__(self):
        super().__init__()
        # Hubert Base 的 7层 1D 卷积参数配置：通道数、卷积核大小、步长
        # 只有第 0 层使用 GroupNorm，后续层不进行 Normalization
        self.conv_layers = nn.ModuleList([
            # Layer 0: Conv1d(1, 512, 10, stride=5, bias=False) + GroupNorm + GELU
            nn.ModuleList([
                nn.Conv1d(1, 512, kernel_size=10, stride=5, bias=False),
                nn.Dropout(p=0.0),
                nn.GroupNorm(num_groups=512, num_channels=512, eps=1e-5, affine=True),
                nn.GELU()
            ]),
            # Layer 1: Conv1d(512, 512, 3, stride=2, bias=False) + GELU
            nn.ModuleList([
                nn.Conv1d(512, 512, kernel_size=3, stride=2, bias=False),
                nn.Dropout(p=0.0),
                nn.GELU()
            ]),
            # Layer 2: Conv1d(512, 512, 3, stride=2, bias=False) + GELU
            nn.ModuleList([
                nn.Conv1d(512, 512, kernel_size=3, stride=2, bias=False),
                nn.Dropout(p=0.0),
                nn.GELU()
            ]),
            # Layer 3: Conv1d(512, 512, 3, stride=2, bias=False) + GELU
            nn.ModuleList([
                nn.Conv1d(512, 512, kernel_size=3, stride=2, bias=False),
                nn.Dropout(p=0.0),
                nn.GELU()
            ]),
            # Layer 4: Conv1d(512, 512, 3, stride=2, bias=False) + GELU
            nn.ModuleList([
                nn.Conv1d(512, 512, kernel_size=3, stride=2, bias=False),
                nn.Dropout(p=0.0),
                nn.GELU()
            ]),
            # Layer 5: Conv1d(512, 512, 2, stride=2, bias=False) + GELU
            nn.ModuleList([
                nn.Conv1d(512, 512, kernel_size=2, stride=2, bias=False),
                nn.Dropout(p=0.0),
                nn.GELU()
            ]),
            # Layer 6: Conv1d(512, 512, 2, stride=2, bias=False) + GELU
            nn.ModuleList([
                nn.Conv1d(512, 512, kernel_size=2, stride=2, bias=False),
                nn.Dropout(p=0.0),
                nn.GELU()
            ])
        ])

    def forward(self, x):
        # x: (B, 1, T)
        for layer in self.conv_layers:
            for submodule in layer:
                x = submodule(x)
        return x


class SelfAttention(nn.Module):
    def __init__(self, embed_dim=768, num_heads=12):
        super().__init__()
        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads
        self.scaling = self.head_dim ** -0.5

        # 投影线性层，与 fairseq 命名保持完全一致
        self.q_proj = nn.Linear(embed_dim, embed_dim)
        self.k_proj = nn.Linear(embed_dim, embed_dim)
        self.v_proj = nn.Linear(embed_dim, embed_dim)
        self.out_proj = nn.Linear(embed_dim, embed_dim)

    def forward(self, x, padding_mask=None):
        # x: (B, T, C)
        B, T, C = x.shape
        
        q = self.q_proj(x).view(B, T, self.num_heads, self.head_dim).transpose(1, 2) # (B, H, T, D)
        k = self.k_proj(x).view(B, T, self.num_heads, self.head_dim).transpose(1, 2) # (B, H, T, D)
        v = self.v_proj(x).view(B, T, self.num_heads, self.head_dim).transpose(1, 2) # (B, H, T, D)

        attn_weights = torch.matmul(q, k.transpose(-2, -1)) * self.scaling # (B, H, T, T)

        if padding_mask is not None:
            # padding_mask shape: (B, T) bool, True 表示 padding 掉
            mask = padding_mask.unsqueeze(1).unsqueeze(2) # (B, 1, 1, T)
            attn_weights = attn_weights.masked_fill(mask, float("-inf"))

        attn_probs = F.softmax(attn_weights, dim=-1)
        output = torch.matmul(attn_probs, v) # (B, H, T, D)
        output = output.transpose(1, 2).contiguous().view(B, T, C)
        output = self.out_proj(output)
        return output


class TransformerEncoderLayer(nn.Module):
    def __init__(self, embed_dim=768, num_heads=12, ffn_dim=3072):
        super().__init__()
        # Post-LN 结构
        self.self_attn = SelfAttention(embed_dim, num_heads)
        self.self_attn_layer_norm = nn.LayerNorm(embed_dim)
        
        self.fc1 = nn.Linear(embed_dim, ffn_dim)
        self.fc2 = nn.Linear(ffn_dim, embed_dim)
        self.final_layer_norm = nn.LayerNorm(embed_dim)

    def forward(self, x, padding_mask=None):
        # x: (B, T, C)
        residual = x
        x = self.self_attn(x, padding_mask=padding_mask)
        x = residual + x
        x = self.self_attn_layer_norm(x)

        residual = x
        x = self.fc2(F.gelu(self.fc1(x)))
        x = residual + x
        x = self.final_layer_norm(x)
        return x


class TransformerEncoder(nn.Module):
    def __init__(self, embed_dim=768, num_heads=12, ffn_dim=3072, num_layers=12):
        super().__init__()
        # 位置卷积编码器：Conv1d(768, 768, 128, padding=64, groups=16) 并在外面包一层 weight_norm
        # 为保持 state_dict 命名对应，将其命名为 pos_conv 且是个 nn.Sequential，第 0 项是 Conv1d
        conv = nn.Conv1d(embed_dim, embed_dim, kernel_size=128, padding=64, groups=16)
        self.pos_conv = nn.Sequential(
            nn.utils.weight_norm(conv, dim=2),
            nn.GELU()
        )
        
        self.layers = nn.ModuleList([
            TransformerEncoderLayer(embed_dim, num_heads, ffn_dim)
            for _ in range(num_layers)
        ])
        
        self.layer_norm = nn.LayerNorm(embed_dim)

    def forward(self, x, padding_mask=None, output_layer=12):
        # x: (B, T, C)
        # 1. 卷积位置编码
        x_t = x.transpose(1, 2) # (B, C, T)
        pos = self.pos_conv(x_t) # (B, C, T)
        # 若由于 padding 截断导致形状稍微不一致，裁剪至输入长度
        pos = pos[..., :x.size(1)]
        x = x + pos.transpose(1, 2) # (B, T, C)

        # Post-LN 模式下，在位置编码之后，进入 layers 循环之前进行全局 layer_norm
        x = self.layer_norm(x)

        # 2. Transformer 编码层循环
        for i, layer in enumerate(self.layers):
            if output_layer is not None and i >= output_layer:
                break
            x = layer(x, padding_mask=padding_mask)
            
        return x


class HubertModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.feature_extractor = FeatureExtractor()
        # 提取器最后一层输出先通过 LayerNorm(512)
        self.layer_norm = nn.LayerNorm(512)
        self.post_extract_proj = nn.Linear(512, 768)
        
        self.encoder = TransformerEncoder()
        
        # 最后的映射层（v1 需要降维，v2 忽略）
        self.final_proj = nn.Linear(768, 256)

    def extract_features(self, source, padding_mask=None, output_layer=12):
        """
        RVC pipeline 调用接口
        """
        # source: (B, T_audio)，必须是 FloatTensor
        x = source.unsqueeze(1) # (B, 1, T_audio)
        
        # 1. Conv 特征提取
        x = self.feature_extractor(x) # (B, 512, T_features)
        
        # 处理 padding_mask 下采样
        if padding_mask is not None:
            if padding_mask.shape[-1] == source.shape[-1]:
                if not padding_mask.any():
                    padding_mask = torch.zeros((source.shape[0], x.shape[2]), dtype=torch.bool, device=source.device)
                else:
                    pm_float = padding_mask.float().unsqueeze(1) # (B, 1, T_audio)
                    pm_down = F.interpolate(pm_float, size=x.shape[2], mode='nearest').squeeze(1)
                    padding_mask = pm_down.bool()

        # 2. 投影与归一化
        x = x.transpose(1, 2) # (B, T_features, 512)
        x = self.layer_norm(x)
        x = self.post_extract_proj(x) # (B, T_features, 768)
        
        # 3. Transformer 编码特征 (Pre-LN)
        x = self.encoder(x, padding_mask=padding_mask, output_layer=output_layer)
        
        # 仿照 fairseq，返回 (features, None)
        return (x, None)
