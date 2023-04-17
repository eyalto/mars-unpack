
import os
import cv2
import numpy as np
from PIL import Image

def buffer_to_png(imgbuffer, width, height, stride, timestamp, outputPath):
    # numpy array, reshape to image and comvert colors
    _image = np.frombuffer(imgbuffer,dtype=np.uint8)
    _image2 = cv2.cvtColor(np.reshape(_image,(int(height * 3 / 2),stride,1)), cv2.COLOR_YUV2RGB_NV12)
    # remove garbage pixels
    _image3 = _image2[:, : width,:]
    img = Image.fromarray(_image3, 'RGB')
    # save the image 
    full_path = os.path.join(outputPath,"{}.png".format(timestamp))
    img.save(full_path)
    return full_path


def buffers_to_depth_and_sigma_png(imgDepthBuffer, imgSigmaBuffer,depthFramesOut, sigmaFramesOut, height, width, timestamp):
    _image = np.frombuffer(imgDepthBuffer,dtype=np.uint8)
    _image2 = np.reshape(_image, (height,width,2))
    # write depth png 
    img = Image.fromarray(_image2, "I;16")
    full_path_depth = os.path.join(depthFramesOut,"{}.png".format(timestamp))
    img.save(full_path_depth)
    # read sigma frame
    imgSigmaArray = np.frombuffer(imgSigmaBuffer,dtype=np.uint8)
    _imgSigma = np.reshape(imgSigmaArray, (height,width))
    # write sigma png
    img2 = Image.fromarray(_imgSigma, mode="P")
    full_path_sigma =  os.path.join(sigmaFramesOut,"{}.png".format(timestamp))
    img2.save(full_path_sigma)
    return [full_path_depth,full_path_sigma]