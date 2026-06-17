# @date 2024-11-25
import torch
import torch.nn as nn


# 定义 Spatial Attention 模块
class SpatialAttention(nn.Module):
    def __init__(self, kernel_size=7):
        super(SpatialAttention, self).__init__()
        self.conv = nn.Conv2d(2, 1, kernel_size=kernel_size, padding=kernel_size // 2, bias=False)
        self.sigmoid = nn.Sigmoid()

    def forward(self, x):
        # 最大池化和平均池化
        max_pool = torch.max(x, dim=1, keepdim=True).values
        avg_pool = torch.mean(x, dim=1, keepdim=True)
        # 拼接池化结果
        pool = torch.cat([max_pool, avg_pool], dim=1)
        # 卷积和 sigmoid 激活
        attention = self.sigmoid(self.conv(pool))
        return x * attention  # 元素相乘


# 定义 Attention DenseNet 模块，替换 Attention 为 Spatial Attention
class AttentionDenseNet(nn.Module):
    def __init__(self, in_channels, growth_rate):
        super(AttentionDenseNet, self).__init__()

        # Conv1 + LeakyReLU
        self.conv1 = nn.Conv2d(in_channels, growth_rate, kernel_size=3, padding=1, bias=False)
        self.relu1 = nn.LeakyReLU(0.2, inplace=True)

        # Conv2 + LeakyReLU
        self.conv2 = nn.Conv2d(growth_rate, growth_rate, kernel_size=3, padding=1, bias=False)
        self.relu2 = nn.LeakyReLU(0.2, inplace=True)

        # Conv3 + LeakyReLU
        self.conv3 = nn.Conv2d(growth_rate, growth_rate, kernel_size=3, padding=1, bias=False)
        self.relu3 = nn.LeakyReLU(0.2, inplace=True)

        # Conv4 + LeakyReLU
        self.conv4 = nn.Conv2d(growth_rate, growth_rate, kernel_size=3, padding=1, bias=False)
        self.relu4 = nn.LeakyReLU(0.2, inplace=True)

        # 替换为 Spatial Attention 模块
        self.spatial_attention = SpatialAttention(kernel_size=7)

        # Conv5 (输出通道恢复到初始输入通道数)
        self.conv5 = nn.Conv2d(growth_rate, in_channels, kernel_size=3, padding=1, bias=False)

    def forward(self, x):
        # 记录初始输入
        residual = x

        # Dense 连接层
        out1 = self.relu1(self.conv1(x))
        out2 = self.relu2(self.conv2(out1))
        out3 = self.relu3(self.conv3(out2))
        out4 = self.relu4(self.conv4(out3))

        # 替换为 Spatial Attention
        out = self.spatial_attention(out4)

        # 输出卷积
        out = self.conv5(out)

        # 加残差连接
        out += residual
        return out


# 测试 Attention DenseNet 模块
if __name__ == "__main__":
    # 创建模型
    model = AttentionDenseNet(in_channels=64, growth_rate=32)

    # 创建一个示例输入
    input_tensor = torch.randn(1, 64, 32, 32)  # (batch size, channels, height, width)

    # 前向传播
    output = model(input_tensor)

    # 打印输入和输出形状
    print("Input shape:", input_tensor.shape)
    print("Output shape:", output.shape)
