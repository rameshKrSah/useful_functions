#!/usr/bin/env python
# coding: utf-8

import os
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import datetime
import csv
import pickle

# local imports
import utils as utl
import filtering as filters
import preprocessing as preprocessing

from argparse import ArgumentParser


participants_folder = ['Part 101C',
 'Part 102C',
 'Part 104C',
 'Part 105C',
 'Part 106C',
 'Part 107C',
 'Part 108C',
 'Part 109C',
 'Part 110C',
 'Part 111C',
 'Part 112C']


# # Details
# The sampling rate for
# - Galvanic Skin Response is 4hz
# - Skin Temperature is 4hz
# - Blood Volume Pulse is 64hz
# - Acceleration is 32hz
# - Heart rate is 1hz
#
# For each sensor csv file, the first row is the timestamp for recording start time
# and in some sensor files the second row is sampling frequency. We can use the
# timestamp to put time values next to each row of values in all sensor files,
# and use this timestamp to extract the window around the tag timestamps.
#
# For window size we can experiment with different values, and we will start
# with 25 seconds window and go upto 10 minutes.
#
# We also need to apply filtering on sensor values. For EDA values,
# 1. First-order BW LPF cut-off frequency 5 Hz to remove noise.
# 2. First-order BW HPF cut-off frequency 0.05 Hz to separate SCR and SCL
#
# and for skin temperature
# 1. Second-order BW LPF frequency of 1 Hz
# 2. Second-order BW HPF frequency of 0.1 Hz
#
#
# Unix time is a system for describing a point in time, and is the number of
# seconds that have elapsed since the Unix epoch, minus leap seconds; the Unix
# epoch is 00:00:00 UTC on 1 January 1970.
#
# Every file except the IBI file has sampling frequency in the second row.
# All files have staring time in UNIX timestamp in the first row.

# Constants
E4_EDA_SF = 4
E4_ACC_SF = 32
E4_BVP_SF = 64
E4_HR_SF = 1
E4_TEMP_SF = 4

EDA_CUTOFF_FREQ = 5.0/ E4_EDA_SF

# 40 minutes, 20 minutes before the event and 20 minutes after the event
tag_segment_length_seconds = 40 * 60

# overlapping window segmentation details 
window_length_seconds = 60
overlap_seconds = 30          # 50% overlap
overlap_percent = 0.5

# data_folder = "../Data/Wearable Devices Study Data/"
# output_folder = "../Processed Data/24 seconds window ADARP/"

def get_sensor_data(file_path):
    """
    Load data from a text file located at file_path.
    :param file_path: path to the text file

    """
    data = []
    try:
        data = np.genfromtxt(file_path, delimiter=',')
    except:
        print("Error reading the file {}".format(file_path))

    return data


def get_tag_timestamps(tag_file):
    """
        Open the tag files and retun the tag timestamps as an array.
    
    :param tag_file: Path to the tags file.
    """

    tag_timestamps = []

    count = 0
    for line in open(tag_file): count += 1

    if count < 2:
        return tag_timestamps

    # print(f"{count - 1} tags in {tag_file}")
    with open(tag_file, "r") as read_file:
        csv_reader = csv.reader(read_file)
        # skip the header line
        next(csv_reader)
        for row in csv_reader:
            unix_time = float(row[0])
            tag_timestamps.append(unix_time)

    return tag_timestamps


def extract_segments_around_tags(data, tags, segment_size):
    """
        Given data array, tags array and window size extract window size segments 
        from the data array around the tags.

    :param data: Data array
    :param tags: An array with tag event times
    :param segment_size: Segment size in seconds

    """
    # return array
    segments = []
    
    # get the start time: expressed as unit timestamp in UTC i.e., seconds from Jan 1 1970
    start_time = data[0]
    
    # get the sampling frequency expressed in Hz
    sampling_freq = data[1]
    
    try:
        if len(start_time):
            start_time = start_time[0]
    except:
        start_time = start_time
    
    try:
        if len(sampling_freq):
            sampling_freq = sampling_freq[0]
    except:
        sampling_freq = sampling_freq

    # get the sensor data and data length
    sensor_data = data[2:]
    data_length = len(sensor_data)

    # the timestamp corresponding to the last data value
    end_time = start_time + (data_length / sampling_freq)

    # the number of data samples before and after the timestamps
    n_obs = int((segment_size // 2) * sampling_freq)

    # for each time stamp in tags
    for timestamp in tags:
        # if the timestamp is within the sensor time array
        if (timestamp >= start_time) & (timestamp <= end_time):
            # how far is the timestamp from the start time.
            difference = int(timestamp - start_time)

            # get the index in the sensor data array, based on the difference of tag timestamp
            position = int(difference * sampling_freq)
            
            # window segment position in the data array
            from_ = position - n_obs
            to_ = position + n_obs

            if (from_ < 0):
                from_ = 0
            if (to_ > data_length):
                to_ = data_length

            # get the data segment
            seg = sensor_data[from_:to_]
            segments.append(seg)

    return segments


def get_eda_data_around_tags(data_folder, tag_timestamps, segment_size):
    """
        Get EDA segments from the EDA CSV file in data_folder with tag_timestamps 
        for segment length of segment_size

    :param data_folder: Path to the folder containing the EDA file
    :param tag_timestamps: An array containing the tag event markers.
    :param segment_size: Segment size in seconds

    """

    # load the data from EDA.csv
    file_path = data_folder + "/EDA.csv"
    sensor_data = get_sensor_data(file_path)

    segments = extract_segments_around_tags(sensor_data, tag_timestamps, segment_size)
    processed_EDA = []
    for p in segments:
        pp = filters.butter_lowpassfilter(np.array(p).ravel(), EDA_CUTOFF_FREQ, E4_EDA_SF, order=2)
        pp = preprocessing.normalization(pp)
        processed_EDA.append(pp)

    return processed_EDA


def get_hr_data_around_tags(data_folder, tag_timestamps, segment_size):
    """
        Get HR segments from the HR CSV file in data_folder with tag_timestamps 
        for segment length of segment_size

    :param data_folder: Path to the folder containing the HR file
    :param tag_timestamps: An array containing the tag event markers.
    :param segment_size: Window size in seconds.

    """

    # load the data from EDA.csv
    file_path = data_folder + "/HR.csv"
    sensor_data = get_sensor_data(file_path)

    return extract_segments_around_tags(sensor_data, tag_timestamps, segment_size)


def get_temp_data_around_tags(data_folder, tag_timestamps, segment_size):
    """
        Get TEMP segments from the TEMP CSV file in data_folder with tag_timestamps 
        for segment length of segment_size

    :param data_folder: Path to the folder containing the TEMP file
    :param tag_timestamps: An array containing the tag event markers.
    :param segment_size: Segment length in seconds.

    """

    # load the data from EDA.csv
    file_path = data_folder + "/TEMP.csv"
    sensor_data = get_sensor_data(file_path)

    return extract_segments_around_tags(sensor_data, tag_timestamps, segment_size)


def get_bvp_data_around_tags(data_folder, tag_timestamps, segment_size):
    """
        Get BVP segments from the BVP CSV file in data_folder with tag_timestamps 
        for segment length of segment_size

    :param data_folder: Path to the folder containing the BVP file
    :param tag_timestamps: An array containing the tag event markers.
    :param segment_size: Segment length in seconds.

    """

    # load the data from EDA.csv
    file_path = data_folder + "/BVP.csv"
    sensor_data = get_sensor_data(file_path)

    return extract_segments_around_tags(sensor_data, tag_timestamps, segment_size)


def get_acc_data_around_tags(data_folder, tag_timestamps, segment_size):
    """
        Get ACC segments from the ACC CSV file in data_folder with tag_timestamps 
        for segment length of segment_size

    :param data_folder: Path to the folder containing the ACC file
    :param tag_timestamps: An array containing the tag event markers.
    :param segment_size: Segment length in seconds.

    """
    # load the data from EDA.csv
    file_path = data_folder + "/ACC.csv"
    sensor_data = get_sensor_data(file_path)

    return extract_segments_around_tags(sensor_data, tag_timestamps, segment_size)

def extract_segments_for_verified_tags(data_folder, tag_timestamps_folder, segment_length, output_folder):
    # data containers
    eda_data = []
    hr_data = []
    acc_data = []
    bvp_data = []
    temp_data = []

    for participants_tags_file in os.listdir(tag_timestamps_folder):
        # get the verified tag for the participants
        tag_events = get_tag_timestamps(tag_timestamps_folder  + participants_tags_file)
        if(len(tag_events) == 0):
            continue

        # print(tag_events)

        # get the participants identifier
        participant_name = participants_tags_file[:9]

        # the original folder with participant data
        participants_data_folder = data_folder + participant_name + "/"

        # subfolders within the participants data folder. 
        subfolders = os.listdir(participants_data_folder)

        # for each sub-folder in the participants folder
        for sub in subfolders:
            sub_folder_path = participants_data_folder + sub

            # get the tag events in this folder
            tag_timestamps = get_tag_timestamps(sub_folder_path + '/tags.csv')
            if(len(tag_timestamps) == 0):
                continue

            # print(tag_timestamps)

            # if there are tag events, and if any verified tags are within this list
            # extract data around the verified tag event timestamp
            print(f"Searching for {tag} in {tag_timestamps}")
            if len(tag_timestamps):
                for tag in tag_events:
                    for stamps in tag_timestamps:
                        if tag - stamps < 10:
                            # first EDA
                            values = get_eda_data_around_tags(sub_folder_path, [stamps], segment_length)
                            if len(values):
                                eda_data.extend(values)

                            # second temperature
                            values = get_temp_data_around_tags(sub_folder_path, [stamps], segment_length)
                            if len(values):
                                temp_data.extend(values)

                            # third bvp
                            values = get_bvp_data_around_tags(sub_folder_path, [stamps], segment_length)
                            if len(values):
                                bvp_data.extend(values)

                            # fourth hr
                            values = get_hr_data_around_tags(sub_folder_path, [stamps], segment_length)
                            if len(values):
                                hr_data.extend(values)

                            # fifth acc
                            values = get_acc_data_around_tags(sub_folder_path, [stamps], segment_length)
                            if len(values):
                                acc_data.extend(values)

    # save the participants data
    # print("Saving data of participants " + p)
    # utl.save_data(output_folder + p + "_EDA_TAG.pkl", np.array(part_eda_data))
    # utl.save_data(output_folder + p + "_TEMP_TAG.pkl", np.array(part_temp_data))
    # utl.save_data(output_folder + p + "_HR_TAG.pkl", np.array(part_hr_data))
    # utl.save_data(output_folder + p + "_BVP_TAG.pkl", np.array(part_bvp_data))
    # utl.save_data(output_folder + p + "_ACC_TAG.pkl", np.array(part_acc_data))

    return np.array(eda_data), np.array(hr_data), np.array(acc_data), np.array(bvp_data), np.array(temp_data)


def extract_data_around_tags(segment_length):
    """
        From the ADARP data folder extract the sensor segments for length of segment_length. 
        EDA, HR, ACC, BVP, and TEMP segemnts are extracted around tag event markers.

    :param segment_length: Size of the segment in seconds.

    """
    eda_data = []
    hr_data = []
    acc_data = []
    bvp_data = []
    temp_data= []

    # for each participants
    for p in participants_folder:
        part_eda_data = []
        part_hr_data = []
        part_acc_data = []
        part_bvp_data = []
        part_temp_data = []

#         print("Extracting data for participants: {}".format(p))
        participants_folder_path = data_folder + p + "/"
        subfolders = os.listdir(participants_folder_path)

        # for each sub-folder in the participants folder
        for sub in subfolders:
            path = participants_folder_path + sub
#             print("For subfolder: {}".format(path))

            # get the tag events in this folder
            tag_timestamps = get_tag_timestamps(path)

            # if there are tag events, get the sensor values
            if len(tag_timestamps):
                # first EDA
                values = get_eda_data_around_tags(path, tag_timestamps, segment_length)
                if len(values):
                    eda_data.extend(values)
                    part_eda_data.extend(values)

                # second temperature
                values = get_temp_data_around_tags(path, tag_timestamps, segment_length)
                if len(values):
                    temp_data.extend(values)
                    part_temp_data.extend(values)

                # third bvp
                values = get_bvp_data_around_tags(path, tag_timestamps, segment_length)
                if len(values):
                    bvp_data.extend(values)
                    part_bvp_data.extend(values)

                # fourth hr
                values = get_hr_data_around_tags(path, tag_timestamps, segment_length)
                if len(values):
                    hr_data.extend(values)
                    part_hr_data.extend(values)

                # fifth acc
                values = get_acc_data_around_tags(path, tag_timestamps, segment_length)
                if len(values):
                    acc_data.extend(values)
                    part_acc_data.extend(values)

        # save the participants data
        print("Saving data of participants " + p)
        utl.save_data(output_folder + p + "_EDA_TAG.pkl", np.array(part_eda_data))
        utl.save_data(output_folder + p + "_TEMP_TAG.pkl", np.array(part_temp_data))
        utl.save_data(output_folder + p + "_HR_TAG.pkl", np.array(part_hr_data))
        utl.save_data(output_folder + p + "_BVP_TAG.pkl", np.array(part_bvp_data))
        utl.save_data(output_folder + p + "_ACC_TAG.pkl", np.array(part_acc_data))

    return np.array(eda_data), np.array(hr_data), np.array(acc_data), np.array(bvp_data), np.array(temp_data)


def get_segments_between_timestamps(data, tag_timestamps, segment_size, segments):
    """
        Extract sensor segments between timestamps. 

    @param data: sensor data array
    @param tag_timestamps: timestamps of tags
    @param segment_size: Length of the segments in seconds
    @param segments: Array to store the extracted segments
    """

    if(len(data) == 0):
        return segments
    
    if len(tag_timestamps) == 0:
        segments.append(data[2:])
        return segments
    else:
        # extract start time, sampling freq, and n_observations
        start_time = data[0]
        sampling_freq = data[1]
        try:
            if len(start_time):
                start_time = start_time[0]
        except:
            start_time = start_time

        try:
            if len(sampling_freq):
                sampling_freq = sampling_freq[0]
        except:
            sampling_freq = sampling_freq

        n_observation = int((segment_size // 2) * sampling_freq)
        
        # create the tags, add the start and end time into tags
        tags = [start_time]
        tags.extend(tag_timestamps)
        tags.append(tags[0] + len(data) / sampling_freq)
        
        # data
        data = data[2:]
        data_length = len(data)
        for i in range(len(tags)):
            j = i + 1
            if j >= len(tags):
                break
            start_tag = tags[i]
            end_tag = tags[j]
#             print("Current tags pair ", (start_tag, end_tag))
            here_ = int((start_tag - start_time) * sampling_freq + n_observation)
            there_ = int((end_tag - start_time) * sampling_freq - n_observation)
#             print("Indices ", (here_, there_))
            # if there are data points between the tags, extract those data points else ignore them
            if((there_ - here_) > 0):
                pp = data[here_:there_]
                segments.append(pp)

        return segments


def not_stressed_data_from_all_files():
    """
        Extract data for not-stressed class from all folders.
    """ 
    eda_data = []
    hr_data = []
    acc_data = []
    bvp_data = []
    temp_data= []
    
    # for each participants
    for p in participants_folder:
        part_eda_data = []
        part_hr_data = []
        part_acc_data = []
        part_bvp_data = []
        part_temp_data = []
        
        print("Extracting data for participants {}".format(p))
        participants_folder_path = data_folder + p + "/"
        subfolders = os.listdir(participants_folder_path)
        
        # for each subfolders in the participant folder
        for sub in subfolders:
            path = participants_folder_path + sub
            # get tag timestamps
            tag_timestamps = get_tag_timestamps(path)
            
            # load the EDA data
            data = get_sensor_data(path+"/EDA.csv")
            part_eda_data = get_segments_between_timestamps(data, tag_timestamps, tag_segment_length_seconds, part_eda_data)

            # HR Segments
            data = get_sensor_data(path+"/HR.csv")
            part_hr_data = get_segments_between_timestamps(data, tag_timestamps, tag_segment_length_seconds, part_hr_data)

            # TEMP Segments
            data = get_sensor_data(path+"/TEMP.csv")
            part_temp_data = get_segments_between_timestamps(data, tag_timestamps,tag_segment_length_seconds, part_temp_data)

            # BVP Segments
            data = get_sensor_data(path+"/BVP.csv")
            part_bvp_data = get_segments_between_timestamps(data, tag_timestamps, tag_segment_length_seconds, part_bvp_data)

            # ACC Segments
            data = get_sensor_data(path+"/ACC.csv")
            part_acc_data = get_segments_between_timestamps(data, tag_timestamps, tag_segment_length_seconds, part_acc_data)
        
        # We filter and normalize the EDA data. 
        processed_EDA =[]
        for segments in part_eda_data:
            ses = eda_filtering.butter_lowpassfilter(np.array(segments).ravel(), EDA_CUTOFF_FREQ, 
                                                                       E4_EDA_SF, order=2)
            ses = eda_preprocessing.normalization(ses)
            processed_EDA.append(ses)
            
        # save the participants data
        print("Saving data of participants " + p)                                          
        save_data(subject_no_tag_folder + p + "_EDA_NO_TAG.pkl", np.array(processed_EDA))
        save_data(subject_no_tag_folder + p + "_TEMP_NO_TAG.pkl", np.array(part_temp_data))
        save_data(subject_no_tag_folder + p + "_HR_NO_TAG.pkl", np.array(part_hr_data))
        save_data(subject_no_tag_folder + p + "_BVP_NO_TAG.pkl", np.array(part_bvp_data))
        save_data(subject_no_tag_folder + p + "_ACC_NO_TAG.pkl", np.array(part_acc_data))
        
        # add the participants data to the whole data
        eda_data.extend(processed_EDA)
        hr_data.extend(part_hr_data)
        temp_data.extend(part_temp_data)
        bvp_data.extend(part_bvp_data)
        acc_data.extend(part_acc_data)
        
        print("Processed part data ", len(processed_EDA))
        print("Total data ", len(eda_data))
        
    return np.array(eda_data), np.array(hr_data), np.array(temp_data), np.array(bvp_data), np.array(acc_data)

def not_stressed_data_from_zero_tags_files():
    """
        Extract data for the not-stress class from folders with zero tag event markers.
    """
    eda_data = []
    hr_data = []
    acc_data = []
    bvp_data = []
    temp_data= []
    
    # for each participants
    for p in participants_folder:
        part_eda_data = []
        part_hr_data = []
        part_acc_data = []
        part_bvp_data = []
        part_temp_data = []
        
        print("Extracting data for participants {}".format(p))
        participants_folder_path = data_folder + p + "/"
        subfolders = os.listdir(participants_folder_path)
        
        # for each subfolders in the participant folder
        for sub in subfolders:
            path = participants_folder_path + sub
            # get tag timestamps
            tag_timestamps = get_tag_timestamps(path)
            
            if len(tag_timestamps) == 0:
                # load the EDA data
                data = get_sensor_data(path+"/EDA.csv")
                part_eda_data.append(data[2:])

                # HR Segments
                data = get_sensor_data(path+"/HR.csv")
                part_hr_data.append(data[2:])
                
                # TEMP Segments
                data = get_sensor_data(path+"/TEMP.csv")
                part_temp_data.append(data[2:])
                
                # BVP Segments
                data = get_sensor_data(path+"/BVP.csv")
                part_bvp_data.append(data[2:])
                
                # ACC Segments
                data = get_sensor_data(path+"/ACC.csv")
                part_acc_data.append(data[2:])
                
        # We filter and normalize the EDA data. 
        processed_EDA =[]
        for segments in part_eda_data:
            ses = eda_filtering.butter_lowpassfilter(np.array(segments).ravel(), EDA_CUTOFF_FREQ, 
                                                                       E4_EDA_SF, order=2)
            ses = eda_preprocessing.normalization(ses)
            processed_EDA.append(ses)
            
        # save the participants data
        print("Saving data of participants " + p)                                          
        save_data(subject_no_tag_folder + p + "_EDA_NO_TAG.pkl", np.array(processed_EDA))
        save_data(subject_no_tag_folder + p + "_TEMP_NO_TAG.pkl", np.array(part_temp_data))
        save_data(subject_no_tag_folder + p + "_HR_NO_TAG.pkl", np.array(part_hr_data))
        save_data(subject_no_tag_folder + p + "_BVP_NO_TAG.pkl", np.array(part_bvp_data))
        save_data(subject_no_tag_folder + p + "_ACC_NO_TAG.pkl", np.array(part_acc_data))
        
        # add the participants data to the whole data
        eda_data.extend(processed_EDA)
        hr_data.extend(part_hr_data)
        temp_data.extend(part_temp_data)
        bvp_data.extend(part_bvp_data)
        acc_data.extend(part_acc_data)
        
        print("Processed part data ", len(processed_EDA))
        print("Total data ", len(eda_data))
        
    return np.array(eda_data), np.array(hr_data), np.array(temp_data), np.array(bvp_data), np.array(acc_data)

def segment_sensor_data(data_array, sample_rate, window_duration, overlap_percent):
    """
        Overlapping segmentation of data.
    @param data_array: Data to be segmented
    @param sample_rate: Sampling frequency
    @param window_duration: Window size in seconds
    @param overlap_percent: Overlap percentage between consequtive windows.
    """

    window_segments = np.zeros((1, sample_rate * window_duration))
    
    # get the window segments
    for dt in data_array:
#         print("Current data length ", len(dt))
        segments = utl.segment_sensor_reading(dt, window_duration, overlap_percent, sample_rate)
        if(len(segments)):
            window_segments = np.concatenate([window_segments, segments])
    
    # return the segments
    window_segments = window_segments[1:, ]
    return window_segments


def extract_data_without_tags(segment_length):

    """
        Extract sensor segments from the ADARP data folder for observation folder that has 
        empty tags file. EDA, HR, ACC, BVP, and TEMP segments are extracted from observation 
        folder that has empty tags file.

    :param segment_length: Segment size in seconds

    """
    eda_data = []
    hr_data = []
    acc_data = []
    bvp_data = []
    temp_data= []

    # for each participants
    for p in participants_folder:
        part_eda_data = []
        part_hr_data = []
        part_acc_data = []
        part_bvp_data = []
        part_temp_data = []

#         print("Extracting data for participants {}".format(p))
        participants_folder_path = data_folder + p + "/"
        subfolders = os.listdir(participants_folder_path)

        # for each subfolders in the participant folder
        for sub in subfolders:
            path = participants_folder_path + sub

            # get tag timestamps
            tag_timestamps = get_tag_timestamps(path)

            # if there are no tags, get sensor values
            if len(tag_timestamps) == 0:
                # EDA Segments
                data = get_sensor_data(path+"/EDA.csv")
                # first entry is the start time and the second row is the sampling frequency
                segments = get_window_segment(data[2:], segment_length, E4_EDA_SF)
                if len(segments):
                    eda_data.extend(segments)
                    part_eda_data.extend(segments)

                # HR Segments
                data = get_sensor_data(path+"/HR.csv")
                segments = get_window_segment(data[2:], segment_length, E4_HR_SF)
                if len(segments):
                    hr_data.extend(segments)
                    part_hr_data.extend(segments)

                # TEMP Segments
                data = get_sensor_data(path+"/TEMP.csv")
                segments = get_window_segment(data[2:], segment_length, E4_TEMP_SF)
                if len(segments):
                    temp_data.extend(segments)
                    part_temp_data.extend(segments)

                # BVP Segments
                data = get_sensor_data(path+"/BVP.csv")
                segments = get_window_segment(data[2:], segment_length, E4_BVP_SF)
                if len(segments):
                    bvp_data.extend(segments)
                    part_bvp_data.extend(segments)

                # ACC Segments
                data = get_sensor_data(path+"/ACC.csv")
                segments = get_window_segment(data[2:], segment_length, E4_ACC_SF)
                if len(segments):
                    acc_data.extend(segments)
                    part_acc_data.extend(segments)

        # save the participants data
        print("Saving data of participants " + p)
        utl.save_data(output_folder + p + "_EDA_NO_TAG.pkl", np.array(part_eda_data))
        utl.save_data(output_folder + p + "_TEMP_NO_TAG.pkl", np.array(part_temp_data))
        utl.save_data(output_folder + p + "_HR_NO_TAG.pkl", np.array(part_hr_data))
        utl.save_data(output_folder + p + "_BVP_NO_TAG.pkl", np.array(part_bvp_data))
        utl.save_data(output_folder + p + "_ACC_NO_TAG.pkl", np.array(part_acc_data))

    return np.array(eda_data), np.array(hr_data), np.array(temp_data), np.array(bvp_data), np.array(acc_data)


# Low Pass Filter removes noise from the EDA data  https://scipy-cookbook.readthedocs.io/items/ButterworthBandpass.html
def eda_lpf(order = 1, fs = 4, cutoff = 5):
    nyq = 0.5 * fs
    low = cutoff / nyq
    b, a = butter(order, low, btype='lowpass', analog=True)
    return b, a

def butter_lowpass_filter_eda(data):
    b, a = eda_lpf()
    y = lfilter(b, a, data)
    return y

# High Pass Filter is used to separate the SCL and SCR components from the EDA signal
def eda_hpf(order = 1, fs = 4, cutoff = 0.05):
    nyq = 0.5 * fs
    high = cutoff / nyq
    b, a = butter(order, high, btype='highpass')
    return b, a

def butter_highpass_filter_eda(data):
    b, a = eda_hpf()
    y = lfilter(b, a, data)
    return y


if __name__ == '__main__':
    parser = ArgumentParser("Data processing ADARP")
    parser.add_argument(
        "-i",
        "--input_directory",
        type=str,
        required=True,
        help="Directory that contains the subject data for ADARP"
    )

    parser.add_argument(
        "-o",
        "--output_directory",
        type=str,
        required=True,
        help="Directory to store the processed data"
    )

    parser.add_argument(
        "-w",
        "--window_size",
        type=int,
        required=True,
        help="window size in seconds"
    )

    args = parser.parse_args()
    # args.input_directory
    # args.output_directory
    # args.window_size