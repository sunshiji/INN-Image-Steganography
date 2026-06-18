import torchvision.utils as vutils

with torch.no_grad():
    for i, data in enumerate(datasets.testloader):
        data = data.to(device)
        print(f"当前提取第{i}张图片：{i}")
        cover = data[data.shape[0] // 2:, :, :, :].to(device)
        secret = data[:data.shape[0] // 2, :, :, :].to(device)
        cover_input = dwt(cover)
        secret_input = dwt(secret)
        input_img = torch.cat((cover_input, secret_input), 1)

        # Forward pass
        output = net(input_img)
        output_steg = output.narrow(1, 0, 4 * c.channels_in)
        output_z = output.narrow(1, 4 * c.channels_in, output.shape[1] - 4 * c.channels_in)
        steg_img = iwt(output_steg)
        backward_z = gauss_noise(output_z.shape, device)

        # Backward pass
        output_rev = torch.cat((output_steg, backward_z), 1)
        bacward_img = net(output_rev, rev=True)
        secret_rev = bacward_img.narrow(1, 4 * c.channels_in, bacward_img.shape[1] - 4 * c.channels_in)
        secret_rev = iwt(secret_rev)
        cover_rev = bacward_img.narrow(1, 0, 4 * c.channels_in)
        cover_rev = iwt(cover_rev)
        
        # Calculate residuals
        resi_cover = (steg_img.to(device) - cover.to(device)) * 20
        resi_secret = (secret_rev.to(device) - secret.to(device)) * 20

        # Save images
        def save_image(tensor, filename):
            # Clamp values to [0,1] range
            tensor = torch.clamp(tensor, 0, 1)
            # Convert from [-1,1] to [0,1] if needed
            if tensor.min() < 0:
                tensor = (tensor + 1) / 2
            vutils.save_image(tensor, filename)
        
        # Save original and processed images
        save_image(cover, c.IMAGE_PATH_cover + '%.5d.png' % i)
        save_image(secret, c.IMAGE_PATH_secret + '%.5d.png' % i)
        save_image(steg_img, c.IMAGE_PATH_steg + '%.5d.png' % i)
        save_image(secret_rev, c.IMAGE_PATH_secret_rev + '%.5d.png' % i)
        
        # Save additional wavelet transformed images if needed
        save_image(cover_input[:,0:3,:,:], c.IMAGE_PATH_cover + 'dwt_%.5d.png' % i)  # Save first 3 channels of DWT
        save_image(cover_rev, c.IMAGE_PATH_cover + 'rev_%.5d.png' % i)
        save_image(resi_cover, c.IMAGE_PATH_cover + 'resi_%.5d.png' % i)
        save_image(resi_secret, c.IMAGE_PATH_secret + 'resi_%.5d.png' % i)