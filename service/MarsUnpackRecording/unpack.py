import itertools
import json
import os
import argparse
import numpy as np
import logging
from PIL import Image
from MarsUnpackRecording.buffer_handlers import *
from multiprocessing import Pool
from functools import partial
import subprocess

logger = logging.getLogger("MARS")

def readSensors(recordingPath):
    return json.load(os.path.join(recordingPath,"SensorRecording.json"))


def readCvData(recordingPath):
    return json.load(os.path.join(recordingPath,"CVRecording.json"))

def processCameraImages(binInputFilePath, outputPath, frames_data, seek_to_byte=0 ):
    logger.debug(" binInputFilePath {} \n outputPath {} \n frames_data {} \n seek_to_byte {}\n".format(binInputFilePath, outputPath, frames_data, seek_to_byte))
    images_paths = []
    #
    with open(binInputFilePath,mode="rb") as binFileInput:
        binFileInput.seek(seek_to_byte)

        for e in frames_data:
            if (e["format"] != "NV12"):
                logger.debug("Skipping non NV12 image...")
                continue

            timestamp = e["timeStampMs"]
            width = e["width"]
            height = e["height"]
            stride = e["stride"]

            # open and read one buffer
            imgbuffer = binFileInput.read(int((height*3/2)*stride))
            filepath = buffer_to_png(imgbuffer,width,height,stride,timestamp,outputPath)
            images_paths.append(filepath)
    #
    return images_paths

def processDepthImages(depthSigmaInputFilePath, depthFramesOut, sigmaFramesOut, frames_data, seek_to_byte=0):
    depth_sigma_paths = []
    with open(depthSigmaInputFilePath, mode="rb") as rawFile:
        rawFile.seek(seek_to_byte)

        for e in frames_data:
            if (e["format"] !=  "GRAY16/8"):
                logger.debug("Skipping non GRAY16/8 depth image...")
                continue

            timestamp = e["timeStampMs"]
            width = e["width"]
            height = e["height"]

            # read depth frame
            imgDepthBuffer = rawFile.read(int(width*height*2))
            # read sigma frame
            imgSigmaBuffer = rawFile.read(int(height*width))
            # save both frames 
            paths = buffers_to_depth_and_sigma_png(imgDepthBuffer, imgSigmaBuffer, depthFramesOut, sigmaFramesOut,
             height=height, width=width, timestamp=timestamp)
            depth_sigma_paths.append(paths)
    #
    return depth_sigma_paths

def setup(input, output):
    sensorsRecordingData = json.load(open(os.path.join(input,"SensorRecording.json"), mode="rb"))
    
    colorFramesOutputPath = os.path.join(output,"colorFrames")
    # make sure output directories exist
    if ( not os.path.exists(colorFramesOutputPath)):
        os.makedirs(colorFramesOutputPath)
        logger.debug("output {} created".format(colorFramesOutputPath))

    depthFramesOutputPath = os.path.join(output,"depthFrames")
    sigmaFramesOutputPath = os.path.join(output,"sigmaFrames")
    if ( not os.path.exists(depthFramesOutputPath)):
        os.makedirs(depthFramesOutputPath)
    if ( not os.path.exists(sigmaFramesOutputPath)):
        os.makedirs(sigmaFramesOutputPath)

    r = {
        "frame_count": sensorsRecordingData["colorFrames"],
        "colorFramesOutputPath": colorFramesOutputPath,
        "depthFramesOutputPath": depthFramesOutputPath,
        "sigmaFramesOutputPath": sigmaFramesOutputPath,
        "concatFilePath": os.path.join(output,"concatfiles.txt"),
        "ffmpegFilePath": os.path.join(output,"sequence.mp4") 
    }

    return r

def unpack(input,output_paths,parallel,verbose):
    rc = 0
    if (verbose):
        logger.setLevel(logging.INFO)

    if parallel == 0:
        parallel = os.cpu_count()

    colorFramesOutputPath = output_paths["colorFramesOutputPath"]
    depthFramesOutputPath = output_paths["depthFramesOutputPath"]
    sigmaFramesOutputPath = output_paths["sigmaFramesOutputPath"]
    # extract images
    sensorsRecordingData = json.load(open(os.path.join(input,"SensorRecording.json"), mode="rb"))
    frames = sensorsRecordingData["colorFrames"]
    frames_count = len(frames)
    frames_per_chunk = int(frames_count/parallel)
    frame = frames[0]
    frame_bytes = int((frame["height"]*3/2)*frame["stride"])

    frames_data_seek_list = [(frames[i:i+frames_per_chunk],i*frame_bytes) for i in range(0,frames_count,frames_per_chunk)]

    binFileInputFilePath = os.path.join(input,"ColorFrames.bin")
    if  os.path.exists(binFileInputFilePath):  
        p = Pool(parallel)
        r = p.starmap(partial(processCameraImages,binFileInputFilePath,colorFramesOutputPath),frames_data_seek_list)
        image_files_paths = list(itertools.chain(*r))
    else:
        logger.warning("Color image frames bin file not found - cannot extract image frames")

    # extract depth
    depth_sigma_frames = sensorsRecordingData["depthFrames"]
    depth_sigma_frames_count = len(depth_sigma_frames)
    depth_sigma_frames_per_chunk = int(depth_sigma_frames_count/parallel)
    depth_sigma_frame = depth_sigma_frames[0]
    depth_sigma_frame_bytes = int(3*depth_sigma_frame["height"]*depth_sigma_frame["width"])

    depth_sigma_frames_data_seek_list = [(depth_sigma_frames[i:i+depth_sigma_frames_per_chunk],i*depth_sigma_frame_bytes) 
    for i in range(0,depth_sigma_frames_count,depth_sigma_frames_per_chunk)]

    # check if bin file exists and extract depth frames    
    if ( (sensorsRecordingData["depthFramesFile"] is not None) and sensorsRecordingData["depthFramesFile"] != ""):
        depthSigmaInputFilePath = os.path.join(input, sensorsRecordingData["depthFramesFile"])
        if os.path.exists(depthSigmaInputFilePath):
            p = Pool(parallel)
            r = p.starmap(partial(processDepthImages,depthSigmaInputFilePath,depthFramesOutputPath, sigmaFramesOutputPath),
            depth_sigma_frames_data_seek_list)
            depth_sigma_files_paths = list(itertools.chain(*r))
        else:
            logger.warning("Depth and Sigma frames bin input file not found - cannot extract depth frames")
    else: 
        logger.warning("Depth and Sigma frames bin file name not found - cannot extract depth frames")

    # # video or not 
    ffmpegFilePath = output_paths["ffmpegFilePath"]
    concatFilePath = output_paths["concatFilePath"]

    file_lines = ["file {}".format(s) for s in image_files_paths]
    with open(concatFilePath, mode="w") as f:
        s = "\nduration 0.066\n".join(file_lines)
        f.write(s)
    
    cmd = "ffmpeg -safe 0 -y -r 15 -f concat -i " + concatFilePath + \
    " -c:v libx264 -x264-params crf=23:bframes=0 -fps_mode passthrough -pix_fmt yuv420p " +  \
    ffmpegFilePath
    try:
        output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
        logger.info("executed command successfully cmd: \n{}".format(cmd))
        logger.info("output:\n{}".format(output.decode()))
    except subprocess.CalledProcessError as e:
        logger.error("error executing command: \n{}".format(cmd))
        logger.error("Command output: {}".format(e.output.decode()))
        rc = -1

    return rc



def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-i','--input',required=True, help="path to input recordings folder")
    parser.add_argument('-o','--output',required=True, help="path to output image folder")
    parser.add_argument('-f','--ffmpeg',default=None, required=False, help="ffmpeg output path")
    parser.add_argument('-p','--parallel', default=0, required=False, help="0 == cpu_count(), 1 not parallel or any other processes number")
    parser.add_argument('-v','--verbose',default=False, required=False, help="debug log level")
    args = parser.parse_args()

    try:
        output_paths = setup(args.input, args.output)
        rc = unpack(args.input, output_paths, args.parallel, args.verbose)
    except:
        rc = 1
    
    return rc

if __name__ == '__main__':
    main()