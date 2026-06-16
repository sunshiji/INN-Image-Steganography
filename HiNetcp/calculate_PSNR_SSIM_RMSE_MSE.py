'''
calculate the PSNR and SSIM.
same as MATLAB's results
'''
import os
import math
import numpy as np
import cv2
import glob
import config as c
from natsort import natsorted
from datetime import datetime


def main():
    # Configurations
    # folder_GT = c.IMAGE_PATH_secret
    # folder_Gen = c.IMAGE_PATH_secret_rev

    
    folder_GT=c.IMAGE_PATH_cover
    folder_Gen=c.IMAGE_PATH_steg
    print(folder_Gen)
    crop_border = 1
    suffix = '_secret_rev'
    test_Y = False  # True: test Y channel only; False: test RGB channels
    psnr_threshold = 40  # PSNR threshold for filtering
    PSNRmax = 0
    PSNR_all = []
    SSIM_all = []
    MSE_all = []
    RMSE_all = []
    skipped_images = []
    img_list = sorted(glob.glob(folder_GT + '/*'))
    img_list = natsorted(img_list)

    if test_Y:
        print('Testing Y channel.')
    else:
        print('Testing RGB channels.')

    print(f'\nPSNR threshold set to {psnr_threshold} dB. Images below this value will be skipped.\n')

    for i, img_path in enumerate(img_list):
        base_name = os.path.splitext(os.path.basename(img_path))[0]
        im_GT = cv2.imread(img_path)

        if im_GT is None:
            print(f"Error: Unable to read image from path: {img_path}")
            continue

        im_GT = im_GT / 255.
        im_Gen = cv2.imread(os.path.join(folder_Gen, base_name + '.png')) / 255.
        # im_Gen = cv2.imread(os.path.join(folder_Gen, base_name + '.'+c.format_train)) / 255.

        if im_Gen is None:
            print(f"Error: Unable to read generated image for {base_name}")
            continue

        if test_Y and im_GT.shape[2] == 3:
            im_GT_in = bgr2ycbcr(im_GT)
            im_Gen_in = bgr2ycbcr(im_Gen)
        else:
            im_GT_in = im_GT
            im_Gen_in = im_Gen

        # Calculate metrics
        PSNR = calculate_psnr(im_GT_in * 255, im_Gen_in * 255)
        if PSNRmax < PSNR:
            PSNRmax = PSNR
        # Skip if PSNR below threshold
        if PSNR < psnr_threshold:
            skipped_images.append((base_name, PSNR))
            print(f'{i + 1:3d} - {base_name:25} \tPSNR: {PSNR:.2f} dB (Below threshold, skipped)')
            continue

        SSIM = calculate_ssim(im_GT_in * 255, im_Gen_in * 255)
        MSE = calculate_mse(im_GT_in * 255, im_Gen_in * 255)
        RMSE = calculate_rmse(im_GT_in * 255, im_Gen_in * 255)

        PSNR_all.append(PSNR)
        SSIM_all.append(SSIM)
        MSE_all.append(MSE)
        RMSE_all.append(RMSE)

        print(f'{i + 1:3d} - {base_name:25} \tPSNR: {PSNR:.2f} dB, '
              f'\tSSIM: {SSIM:.4f}, \tMSE: {MSE:.2f}, \tRMSE: {RMSE:.2f}')

    # Print summary
    if PSNR_all:
        print('\n=== Valid Results Summary ===')
        print(f'dataset: {c.dataset}')
        print(f'Average PSNR: {sum(PSNR_all) / len(PSNR_all):.2f} dB')
        print(f'Average SSIM: {sum(SSIM_all) / len(SSIM_all):.4f}')
        print(f'Average MSE: {sum(MSE_all) / len(MSE_all):.2f}')
        print(f'Average RMSE: {sum(RMSE_all) / len(RMSE_all):.2f}')
        print(f'Max PSNR: {PSNRmax:.2f}')

    if skipped_images:
        print('\n=== Skipped Images (PSNR < 40 dB) ===')
        for img, psnr in skipped_images:
            print(f'{img:25} \tPSNR: {psnr:.2f} dB')

    # Save results to file
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open('/home/sunshiji/githubCode/HiNet/results.txt', 'a') as f:
        f.write(f'\n\n{c.dataset} Results recorded at: {timestamp}\n')
        f.write(f'PSNR threshold: {psnr_threshold} dB\n')

        if PSNR_all:
            f.write('\n=== Valid Results ===\n')
            for idx, (p, s, m, r) in enumerate(zip(PSNR_all, SSIM_all, MSE_all, RMSE_all)):
                f.write(f'{idx + 1:2d} - {str(idx + 1).zfill(5)} \tPSNR: {p:.2f} dB, '
                        f'\tSSIM: {s:.4f}, \tMSE: {m:.2f}, \tRMSE: {r:.2f}\n')

            f.write('\nAverages:\n')
            f.write(f'PSNR: {sum(PSNR_all) / len(PSNR_all):.2f} dB\n')
            f.write(f'SSIM: {sum(SSIM_all) / len(SSIM_all):.4f}\n')
            f.write(f'MSE: {sum(MSE_all) / len(MSE_all):.2f}\n')
            f.write(f'RMSE: {sum(RMSE_all) / len(RMSE_all):.2f}\n')
            f.write(f'Max PSNR: {PSNRmax:.2f} dB\n')

        if skipped_images:
            f.write('\n=== Skipped Images ===\n')
            for img, psnr in skipped_images:
                f.write(f'{img:25} \tPSNR: {psnr:.2f} dB\n')


def calculate_psnr(img1, img2):
    img1 = img1.astype(np.float64)
    img2 = img2.astype(np.float64)
    mse = np.mean((img1 - img2) ** 2)
    if mse == 0:
        return float('inf')
    return 20 * math.log10(255.0 / math.sqrt(mse))


def ssim(img1, img2):
    C1 = (0.01 * 255) ** 2
    C2 = (0.03 * 255) ** 2

    img1 = img1.astype(np.float64)
    img2 = img2.astype(np.float64)
    kernel = cv2.getGaussianKernel(11, 1.5)
    window = np.outer(kernel, kernel.transpose())

    mu1 = cv2.filter2D(img1, -1, window)[5:-5, 5:-5]
    mu2 = cv2.filter2D(img2, -1, window)[5:-5, 5:-5]
    mu1_sq = mu1 ** 2
    mu2_sq = mu2 ** 2
    mu1_mu2 = mu1 * mu2
    sigma1_sq = cv2.filter2D(img1 ** 2, -1, window)[5:-5, 5:-5] - mu1_sq
    sigma2_sq = cv2.filter2D(img2 ** 2, -1, window)[5:-5, 5:-5] - mu2_sq
    sigma12 = cv2.filter2D(img1 * img2, -1, window)[5:-5, 5:-5] - mu1_mu2

    ssim_map = ((2 * mu1_mu2 + C1) * (2 * sigma12 + C2)) / ((mu1_sq + mu2_sq + C1) *
                                                            (sigma1_sq + sigma2_sq + C2))
    return ssim_map.mean()


def calculate_ssim(img1, img2):
    if not img1.shape == img2.shape:
        raise ValueError('Input images must have the same dimensions.')
    if img1.ndim == 2:
        return ssim(img1, img2)
    elif img1.ndim == 3:
        if img1.shape[2] == 3:
            ssims = []
            for i in range(3):
                ssims.append(ssim(img1, img2))
            return np.array(ssims).mean()
        elif img1.shape[2] == 1:
            return ssim(np.squeeze(img1), np.squeeze(img2))
    else:
        raise ValueError('Wrong input image dimensions.')


def calculate_mse(img1, img2):
    img1 = img1.astype(np.float64)
    img2 = img2.astype(np.float64)
    return np.mean((img1 - img2) ** 2)


def calculate_rmse(img1, img2):
    return np.sqrt(calculate_mse(img1, img2))


def bgr2ycbcr(img, only_y=True):
    in_img_type = img.dtype
    img.astype(np.float32)
    if in_img_type != np.uint8:
        img *= 255.
    if only_y:
        rlt = np.dot(img, [24.966, 128.553, 65.481]) / 255.0 + 16.0
    else:
        rlt = np.matmul(img, [[24.966, 112.0, -18.214], [128.553, -74.203, -93.786],
                              [65.481, -37.797, 112.0]]) / 255.0 + [16, 128, 128]
    if in_img_type == np.uint8:
        rlt = rlt.round()
    else:
        rlt /= 255.
    return rlt.astype(in_img_type)


if __name__ == '__main__':
    main()
