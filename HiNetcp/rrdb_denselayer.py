import torch.nn as nn
import modules.module_util as mutil
import add.res_ab as res
import torch



# class ResidualDenseBlock_out(nn.Module):
#     def __init__(self, input, output, bias=True):
#         super(ResidualDenseBlock_out, self).__init__()
#         self.conv1 = nn.Conv2d(input, 32, 3, 1, 1, bias=bias)
#         self.conv2 = nn.Conv2d(input + 32, 32, 3, 1, 1, bias=bias)
#         self.conv3 = nn.Conv2d(input + 2 * 32, 32, 3, 1, 1, bias=bias)
#         self.conv4 = nn.Conv2d(input + 3 * 32, 32, 3, 1, 1, bias=bias)
#         self.conv5 = nn.Conv2d(input + 4 * 32, output, 3, 1, 1, bias=bias)
#         self.res = res.Residual_Attention_Block(input, output)
#         self.lrelu = nn.LeakyReLU(inplace=True)
#         # mutil.initialize_weights([self.res], 0.)

#     def forward(self, x):
#         x1 = self.lrelu(self.conv1(x))
#         x2 = self.lrelu(self.conv2(torch.cat((x, x1), 1)))
#         x3 = self.lrelu(self.conv3(torch.cat((x, x1, x2), 1)))
#         x4 = self.lrelu(self.conv4(torch.cat((x, x1, x2, x3), 1)))
#         x5 = self.conv5(torch.cat((x, x1, x2, x3, x4), 1))
#         # print(f"1x1:{x1.shape}")
#         # print(f"1x2:{x2.shape}")
#         # print(f"1x3:{x3.shape}")
#         # print(f"1x4:{x4.shape}")
#         # print(f"1x5:{x5.shape}")
#         x = self.res(x5)
#         # x = self.lrelu(res)
#         return x
# 0411训练 改进 添加 conv6初始化
class ResidualDenseBlock_out(nn.Module):
    def __init__(self, input, output, bias=True):
        super(ResidualDenseBlock_out, self).__init__()
        self.conv1 = nn.Conv2d(input, 32, 3, 1, 1, bias=bias)
        self.conv2 = nn.Conv2d(input + 32, 32, 3, 1, 1, bias=bias)
        self.conv3 = nn.Conv2d(input + 2 * 32, 32, 3, 1, 1, bias=bias)
        self.conv4 = nn.Conv2d(input + 3 * 32, 32, 3, 1, 1, bias=bias)
        self.conv5 = nn.Conv2d(input + 4 * 32, 32, 3, 1, 1, bias=bias)
        self.conv6 = nn.Conv2d(input + 5 * 32, output, 3, 1, 1, bias=bias)
        self.res = res.Residual_Attention_Block(input, output)
        self.lrelu = nn.LeakyReLU(inplace=True)
        # mutil.initialize_weights([self.conv6], 0.)

    def forward(self, x):
        x1 = self.lrelu(self.conv1(x))
        x2 = self.lrelu(self.conv2(torch.cat((x, x1), 1)))
        x3 = self.lrelu(self.conv3(torch.cat((x, x1, x2), 1)))
        x4 = self.lrelu(self.conv4(torch.cat((x, x1, x2, x3), 1)))
        x5 = self.lrelu(self.conv5(torch.cat((x, x1, x2, x3,x4), 1)))
        x6 = self.conv6(torch.cat((x, x1, x2, x3, x4,x5), 1))
        # print(f"1x1:{x1.shape}")
        # print(f"1x2:{x2.shape}")
        # print(f"1x3:{x3.shape}")
        # print(f"1x4:{x4.shape}")
        # print(f"1x5:{x5.shape}")
        x= self.res(x6)
        # x = self.lrelu(res)
        return x
# class ResidualDenseBlock_out(nn.Module):
#     def __init__(self, input, output, bias=True):
#         super(ResidualDenseBlock_out, self).__init__()
#         self.conv1 = nn.Conv2d(input, 32, 3, 1, 1, bias=bias)
#         self.conv2 = nn.Conv2d(input + 32, 32, 3, 1, 1, bias=bias)
#         self.conv3 = nn.Conv2d(input + 2 * 32, 32, 3, 1, 1, bias=bias)
#         self.conv4 = nn.Conv2d(input + 3 * 32, 32, 3, 1, 1, bias=bias)
#         self.conv5 = nn.Conv2d(input + 4 * 32, 32, 3, 1, 1, bias=bias)
#         self.conv6 = nn.Conv2d(input + 5 * 32, output, 3, 1, 1, bias=bias)
#         self.res = res.Residual_Attention_Block(input, output)
#         self.lrelu = nn.LeakyReLU(inplace=True)
#         # mutil.initialize_weights([self.res], 0.)

#     def forward(self, x):
#         x1 = self.lrelu(self.conv1(x))
#         x2 = self.lrelu(self.conv2(torch.cat((x, x1), 1)))
#         x3 = self.lrelu(self.conv3(torch.cat((x, x1, x2), 1)))
#         x4 = self.lrelu(self.conv4(torch.cat((x, x1, x2, x3), 1)))
#         x5 = self.lrelu(self.conv5(torch.cat((x, x1, x2, x3,x4), 1)))
#         x6 = self.conv6(torch.cat((x, x1, x2, x3, x4,x5), 1))
#         # print(f"1x1:{x1.shape}")
#         # print(f"1x2:{x2.shape}")
#         # print(f"1x3:{x3.shape}")
#         # print(f"1x4:{x4.shape}")
#         # print(f"1x5:{x5.shape}")
#         x = self.res(x6)
#         # x = self.lrelu(res)
#         return x
    # 3 Test the model

# if __name__ == "__main__":
#     input_channels = 12  # Example: RGB input
#     output_channels = 12  # Arbitrary output channels for testing
#     batch_size = 16  # Batch size for testing
#     height, width = 112, 112  # Input image size
#
#     # Create a random input tensor of shape (batch_size, input_channels, height, width)
#     #
#     x = torch.randn(batch_size, input_channels, height, width)
#
#     # Instantiate the model
#     model = ResidualDenseBlock_out(input_channels, output_channels)
#     print(model)
#     # Perform a forward pass
#     output = model(x)
#
#     # Print the output shape to verify
#     print(f"Output shape: {output.shape}")
