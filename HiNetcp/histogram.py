import cv2
import matplotlib.pyplot as plt

# 读取图像（替换为你自己的图像路径）
cover_img = cv2.imread('/home/sunshiji/githubCode/HiNet/myImage/cover/00046.png')
stego_img = cv2.imread('/home/sunshiji/githubCode/HiNet/myImage/steg/00046.png')

# OpenCV读取为BGR，无需转换用于直方图计算，但若用于显示，需要转换为RGB
cover_display = cv2.cvtColor(cover_img, cv2.COLOR_BGR2RGB)
stego_display = cv2.cvtColor(stego_img, cv2.COLOR_BGR2RGB)

# 定义颜色和图例
colors = ('b', 'g', 'r')
channel_names = ('Blue', 'Green', 'Red')

plt.figure(figsize=(16, 4))

# 显示 Cover 图像
plt.subplot(1, 4, 1)
plt.imshow(cover_display)
# plt.title('Cover Image')
plt.axis('off')

# 显示 Stego 图像
plt.subplot(1, 4, 2)
plt.imshow(stego_display)
# plt.title('Stego Image')
plt.axis('off')

# Cover 图像直方图
plt.subplot(1, 4, 3)
for i, color in enumerate(colors):
    hist = cv2.calcHist([cover_img], [i], None, [256], [0, 256])
    plt.bar(range(256), hist.ravel(), color=color, alpha=0.4, label=channel_names[i])
# plt.title("Cover Histogram")
plt.legend()

# Stego 图像直方图
plt.subplot(1, 4, 4)
for i, color in enumerate(colors):
    hist = cv2.calcHist([stego_img], [i], None, [256], [0, 256])
    plt.bar(range(256), hist.ravel(), color=color, alpha=0.4, label=channel_names[i])
# plt.title("Stego Histogram")
plt.legend()

plt.tight_layout()

# 保存图像
plt.savefig('/home/sunshiji/githubCode/HiNet/color_histograms_comparison.png', dpi=300)
plt.show()
