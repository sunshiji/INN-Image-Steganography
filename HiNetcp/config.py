# Super parameters
clamp = 2.0
channels_in = 3
log10_lr = -5.0
lr = 10 ** log10_lr
epochs = 1000
# weight_decay = 1e-5
weight_decay = 1e-6
init_scale = 0.01
seed=42
lamda_reconstruction = 5
lamda_guide = 1
lamda_low_frequency = 1
device_ids = [0]
device_id = 0
# Train:
batch_size =8
cropsize = 224
betas = (0.5, 0.999)
weight_step = 50
gamma = 0.5

# Val:
cropsize_val = 1024
batchsize_val = 2
shuffle_val = False
val_freq = 20

# cropsize_val = 224
# batchsize_val = 2
# shuffle_val = False
# val_freq = 20

# Dataset
dataset='DIV2K'
TRAIN_PATH = '/home/sunshiji/githubCode/data/DIV2K/DIV2K_train_HR/'
VAL_PATH = '/home/sunshiji/githubCode/data/DIV2K/DIV2K_valid_HR/'
format_train = 'png'
format_val = 'png'
# dataset = "COCO"
# TRAIN_PATH = '/home/sunshiji/githubCode/data/COCO/train2017/'
# VAL_PATH = '/home/sunshiji/githubCode/data/COCO/val2017/'
# format_train = 'jpg'
# format_val = 'jpg'
# dataset = "ILSVRC1k"
# TRAIN_PATH = '/home/sunshiji/githubCode/data/ILSVRC1k/train1000/'
# VAL_PATH = '/home/sunshiji/githubCode/data/ILSVRC1k/valid1000/'
# format_train = 'JPEG'
# format_val = 'JPEG'

# Display and logging:
loss_display_cutoff = 2.0
loss_names = ['L', 'lr']
silent = False
live_visualization = False
progress_bar = False

# # Saving checkpoints:
# import datetime
# import os
# current_time = datetime.datetime.now()
# # 将日期和时间格式化为字符串，例如 '2023-12-04_12-00'
# formatted_time = current_time.strftime('%Y_%m_%d_%H_%M')
# MODEL_PATH = os.path.join('/home/sunshiji/githubCode/HiNet/model/', formatted_time)
# if not os.path.exists(MODEL_PATH):
#     os.makedirs(MODEL_PATH)
# MODEL_PATH = '/home/sunshiji/githubCode/HiNet/model/20250405/'
# MODEL_PATH = '/home/sunshiji/githubCode/HiNet/model/20250420_IL/'
# MODEL_PATH = '/home/sunshiji/githubCode/HiNet/model/20250416_coco/'
MODEL_PATH = '/home/sunshiji/githubCode/HiNet/model/20250527_div/'
checkpoint_on_error = True
SAVE_freq = 20
# IMAGE_PATH = '/home/sunshiji/githubCode/HiNet/image/DIV2k_s/'
# IMAGE_PATH = '/home/sunshiji/githubCode/HiNet/image/ILSVRC1k_s/'
# IMAGE_PATH = '/home/sunshiji/githubCode/HiNet/image/COCO/'
IMAGE_PATH='/home/sunshiji/githubCode/HiNet/myImage/'
IMAGE_PATH_cover = IMAGE_PATH + 'cover/'
IMAGE_PATH_secret = IMAGE_PATH + 'secret/'
IMAGE_PATH_steg = IMAGE_PATH + 'steg/'
IMAGE_PATH_secret_rev = IMAGE_PATH + 'secret-rev/'

# Load:
# suffix = 'model_checkpoint_02000.pt'
suffix = 'model_best_s.pt'
# suffix='model_best_train_loss.pt'
# suffix='model_best_s_20250416.pt'
tain_next = True
trained_epoch = 0
