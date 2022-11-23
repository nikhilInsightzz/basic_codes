from tendo import singleton
me = singleton.SingleInstance()

import os
import PySpin
import sys
import shutil
import time 
import subprocess
#For logging error
import logging
import traceback
import datetime

import cv2
#Logging module
camlogger = None
logging.basicConfig(filename="FLAIR_SEQ_.log",filemode='a',format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
camlogger=logging.getLogger("FLAIR_SEQ_")
camlogger.setLevel(logging.CRITICAL) #CRITICAL #DEBUG

SIDE1_DEVICE = "21451936"
SIDE2_DEVICE = "21451940"

#DB credentials
import pymysql
db_user = "root"
db_pass = "insightzz123"
db_host = "localhost"
db_name = "CCR3_DB"

processID = os.getpid()
print("This process has the PID", processID)

def updateProcessId(processId):
    try:
        db_update = pymysql.connect(host=db_host,    # your host, usually localhost
                        user=db_user,         # your username
                        passwd=db_pass,  # your password
                        db=db_name)
        cur = db_update.cursor()
        query = f"UPDATE PROCESS_ID_TABLE set PROCESS_ID = {str(processId)} where PROCESS_NAME = 'FRAME_CAPTURE_NUC1'"
        cur.execute(query)
        db_update.commit()
        cur.close()
        db_update.close()
        #print(data_set)
    except Exception as e:
        print(f"Exception in update process id : {e}")
        cur.close()

def update_health(item, status):
    try:
        db_update = pymysql.connect(host=db_host,    # your host, usually localhost
                     user=db_user,         # your username
                     passwd=db_pass,  # your password
                     db=db_name)
        cur = db_update.cursor()
        query = f"UPDATE SYSTEM_HEALTH_TABLE set HEALTH = '{status}' where ITEM = '{item}'"
        cur.execute(query)
        db_update.commit()
        cur.close()
        db_update.close()
    except Exception as e:
        print(f"Exception in update process id : {e}")
        cur.close()

def configure_exposure(cam, exposure_value):
    print('*** CONFIGURING EXPOSURE ***\n')

    try:
        result = True

        if cam.ExposureAuto.GetAccessMode() != PySpin.RW:
            print('Unable to disable automatic exposure. Aborting...')
            return False

        cam.ExposureAuto.SetValue(PySpin.ExposureAuto_Off)
        print('Automatic exposure disabled...')

        if cam.ExposureTime.GetAccessMode() != PySpin.RW:
            print('Unable to set exposure time. Aborting...')
            return False

        # Ensure desired exposure time does not exceed the maximum
        exposure_time_to_set = exposure_value
        exposure_time_to_set = min(cam.ExposureTime.GetMax(), exposure_time_to_set)
        cam.ExposureTime.SetValue(exposure_time_to_set)
        print('Shutter time set to %s us...\n' % exposure_time_to_set)

    except PySpin.SpinnakerException as ex:
        print('Error: %s' % ex)
        result = False

    return result

def acquire_images(cam_list):
    """
    This function acquires and saves 10 images from each device.

    :param cam_list: List of cameras
    :type cam_list: CameraList
    :return: True if successful, False otherwise.
    :rtype: bool
    """

    print('*** IMAGE ACQUISITION ***\n')
    try:
        result = True

        # Prepare each camera to acquire images
        #
        # *** NOTES ***
        # For pseudo-simultaneous streaming, each camera is prepared as if it
        # were just one, but in a loop. Notice that cameras are selected with
        # an index. We demonstrate pseduo-simultaneous streaming because true
        # simultaneous streaming would require multiple process or threads,
        # which is too complex for an example.
        #

        for i, cam in enumerate(cam_list):

            # Set acquisition mode to continuous
            node_acquisition_mode = PySpin.CEnumerationPtr(cam.GetNodeMap().GetNode('AcquisitionMode'))
            if not PySpin.IsAvailable(node_acquisition_mode) or not PySpin.IsWritable(node_acquisition_mode):
                print('Unable to set acquisition mode to continuous (node retrieval; camera %d). Aborting... \n' % i)
                return False

            node_acquisition_mode_continuous = node_acquisition_mode.GetEntryByName('Continuous')
            if not PySpin.IsAvailable(node_acquisition_mode_continuous) or not PySpin.IsReadable(
                    node_acquisition_mode_continuous):
                print('Unable to set acquisition mode to continuous (entry \'continuous\' retrieval %d). \
                Aborting... \n' % i)
                return False

            acquisition_mode_continuous = node_acquisition_mode_continuous.GetValue()

            node_acquisition_mode.SetIntValue(acquisition_mode_continuous)

            print('Camera %d acquisition mode set to continuous...' % i)

            # Begin acquiring images
            node_device_serial_number = PySpin.CStringPtr(cam.GetTLDeviceNodeMap().GetNode('DeviceSerialNumber'))
            device_serial_number = node_device_serial_number.GetValue()
            print(f"device_serial_number : {device_serial_number}")
            if device_serial_number == SIDE2_DEVICE:
                if not configure_exposure(cam, 5000.0):
                    return False
            if device_serial_number == SIDE1_DEVICE:
                if not configure_exposure(cam, 5000.0):
                    return False
            cam.BeginAcquisition()

            print('Camera %d started acquiring images...' % i)

            print()

        # Retrieve, convert, and save images for each camera
        #
        # *** NOTES ***
        # In order to work with simultaneous camera streams, nested loops are
        # needed. It is important that the inner loop be the one iterating
        # through the cameras; otherwise, all images will be grabbed from a
        # single camera before grabbing any images from another.
        
        #for n in range(NUM_IMAGES):
        
        side1_once1 = True
        side1_once2 = True
        side2_once1 = True
        side2_once2 = True

        t2Config = 0
        configTimer = 1
        timerBool = False            

        while True:
            t = int(time.time()*1000)
            t1Config = time.time()
            if (t1Config - t2Config) > configTimer:
                timerBool = True
                t2Config = t1Config
            
            try:
                for i, cam in enumerate(cam_list):
                    # Retrieve device serial number for filename
                    node_device_serial_number = PySpin.CStringPtr(cam.GetTLDeviceNodeMap().GetNode('DeviceSerialNumber'))

                    if PySpin.IsAvailable(node_device_serial_number) and PySpin.IsReadable(node_device_serial_number):
                        device_serial_number = node_device_serial_number.GetValue()
                        #print('Camera %d serial number set to %s...' % (i, device_serial_number))

                    # for keeping rgb value constant
                    ptrRgbTransformLightSource = PySpin.CEnumerationPtr(cam.GetNodeMap().GetNode("RgbTransformLightSource"))
                    ptrRgbTransformationLightSourceWarm = ptrRgbTransformLightSource.GetEntryByName("WarmFluorescent3000K") #Daylight5000K #WarmFluorescent3000K
                    ptrRgbTransformLightSource.SetIntValue(ptrRgbTransformationLightSourceWarm.GetValue())

                    # Retrieve next received image and ensure image completion
                    image_result = cam.GetNextImage(100)

                    if image_result.IsIncomplete():
                        print('Image incomplete with image status %d ... \n' % image_result.GetImageStatus())
                    else:
                        # Print image information
                        width = image_result.GetWidth()
                        height = image_result.GetHeight()
                        #print('Camera %d grabbed image %d, width = %d, height = %d' % (i, n, width, height))

                        # Convert image to mono 8
                        #image_converted = image_result.Convert(PySpin.PixelFormat_Mono8, PySpin.HQ_LINEAR)

                        image_converted = image_result.Convert(PySpin.PixelFormat_BGR8)
                        width = image_result.GetWidth()
                        height = image_result.GetHeight()
                        rgb_array = image_converted.GetData()
                        rgb_array = rgb_array.reshape(height, width, 3)
                        image_nd = rgb_array

                        # Create a unique filename
                        if device_serial_number == SIDE1_DEVICE:
                            filename = 'CAM1/IMG_'+".jpg"
                            if timerBool == True:
                                cv2.imwrite(filename, image_nd)
                                shutil.move("CAM1/IMG_"+".jpg", "CAM1/TMP/IMG_"+".jpg") 
                                # #=========== SENDING DATETIME NAME IMAGE FOR DATE ANALYSIS ================#
                                datefilename = f"IMAGE_DATA_CAM/cam1_{datetime.datetime.now().strftime('%Y-%m-%d_%H:%M:%S.%f')}.jpg"
                                #shutil.copy("CAM1/TMP/IMG_"+".jpg", datefilename)


                            side1_once1 = True
                            if side1_once2 == True:
                                update_health("CAM1","OK")
                                # update_cam_status("SIDE1_POST","YES")
                                camlogger.critical("SIDE1 CAM is connected")
                                print("SIDE1 CAM is connected")
                                side1_once2 = False
                            
                        if device_serial_number == SIDE2_DEVICE:
                            filename = 'CAM2/IMG_'+".jpg"
                            if timerBool == True:
                                cv2.imwrite(filename, image_nd)
                                shutil.move("CAM2/IMG_"+".jpg", "CAM2/TMP/IMG_"+".jpg") 
                                # #=========== SENDING DATETIME NAME IMAGE FOR DATE ANALYSIS ================#
                                datefilename = f"IMAGE_DATA_CAM/cam2_{datetime.datetime.now().strftime('%Y-%m-%d_%H:%M:%S.%f')}.jpg"
                                #shutil.copy("CAM2/TMP/IMG_"+".jpg", datefilename)
                                timerBool = False        

                            side2_once1 = True
                            if side2_once2 == True:
                                update_health("CAM2","OK")
                                # update_cam_status("SIDE2_POST","YES")
                                camlogger.critical("SIDE2 CAM is connected")
                                print("SIDE2 CAM is connected")
                                side2_once2 = False

                        # Save image
                        #image_converted.Save(filename)
                        #print('Image saved at %s' % filename)
                    # time.sleep(0.6)

                    # Release image
                    image_result.Release()
                    
            except PySpin.SpinnakerException as ex:
                if side1_once1:
                    side1_once2 = True
                    # update_health("CAM1","NOTOK")
                    # update_cam_status("SIDE1_POST","NO")
                    camlogger.critical("SIDE1 CAM is not connected")
                    camlogger.critical(ex)
                    side1_once2 = True
                if side2_once1:
                    side2_once2 = True
                    # update_health("CAM2","NOTOK")
                    # update_cam_status("SIDE2_POST","NO")
                    camlogger.critical("SIDE2 CAM is not connected")
                    camlogger.critical(ex)
                    side2_once2 = True
                print('Error: %s' % ex)
                result = False
            #print(f"time for one sequence : {int(time.time()*1000) - t}")

        # End acquisition for each camera
        #
        # *** NOTES ***
        # Notice that what is usually a one-step process is now two steps
        # because of the additional step of selecting the camera. It is worth
        # repeating that camera selection needs to be done once per loop.
        #
        # It is possible to interact with cameras through the camera list with
        # GetByIndex(); this is an alternative to retrieving cameras as
        # CameraPtr objects that can be quick and easy for small tasks.
        for cam in cam_list:

            # End acquisition
            cam.EndAcquisition()

    except PySpin.SpinnakerException as ex:
        update_health("CAM1","NOTOK")
        # update_cam_status("SIDE1_POST","NO")
        camlogger.critical("SIDE1 CAM is not connected")
        print("SIDE1 CAM is connected")
        update_health("CAM2","NOTOK")
        # update_cam_status("SIDE2_POST","NO")
        camlogger.critical("SIDE2 CAM is not connected")
        print("SIDE2 CAM is connected")

        camlogger.critical('Error: %s' % ex)
        print('Error: %s' % ex)
        result = False

    return result

def print_device_info(nodemap, cam_num):
    """
    This function prints the device information of the camera from the transport
    layer; please see NodeMapInfo example for more in-depth comments on printing
    device information from the nodemap.

    :param nodemap: Transport layer device nodemap.
    :param cam_num: Camera number.
    :type nodemap: INodeMap
    :type cam_num: int
    :returns: True if successful, False otherwise.
    :rtype: bool
    """

    print('Printing device information for camera %d... \n' % cam_num)

    try:
        result = True
        node_device_information = PySpin.CCategoryPtr(nodemap.GetNode('DeviceInformation'))

        if PySpin.IsAvailable(node_device_information) and PySpin.IsReadable(node_device_information):
            features = node_device_information.GetFeatures()
            for feature in features:
                node_feature = PySpin.CValuePtr(feature)
                print('%s: %s' % (node_feature.GetName(),
                                  node_feature.ToString() if PySpin.IsReadable(node_feature) else 'Node not readable'))

        else:
            print('Device control information not available.')
        print()

    except PySpin.SpinnakerException as ex:
        print('Error: %s' % ex)
        return False

    return result

def getSerialNumber(cam):
    device_serial_number = ''
    nodemap_tldevice = cam.GetTLDeviceNodeMap()
    node_device_serial_number = PySpin.CStringPtr(nodemap_tldevice.GetNode('DeviceSerialNumber'))
    if PySpin.IsAvailable(node_device_serial_number) and PySpin.IsReadable(node_device_serial_number):
        device_serial_number = node_device_serial_number.GetValue()
        print('Device serial number retrieved as %s...' % device_serial_number)
    return device_serial_number   

def run_multiple_cameras(cam_list):
    """
    This function acts as the body of the example; please see NodeMapInfo example
    for more in-depth comments on setting up cameras.

    :param cam_list: List of cameras
    :type cam_list: CameraList
    :return: True if successful, False otherwise.
    :rtype: bool
    """
    try:
        result = True

        # Retrieve transport layer nodemaps and print device information for
        # each camera
        # *** NOTES ***
        # This example retrieves information from the transport layer nodemap
        # twice: once to print device information and once to grab the device
        # serial number. Rather than caching the nodem#ap, each nodemap is
        # retrieved both times as needed.
        print('*** DEVICE INFORMATION ***\n')

        device_list = []
        for i, cam in enumerate(cam_list):
            # Retrieve TL device nodemap
            nodemap_tldevice = cam.GetTLDeviceNodeMap()
            #adding device number to the device list 
            device_list.append(getSerialNumber(cam))
            # Print device information
            result &= print_device_info(nodemap_tldevice, i)
            
        for device in device_list:
            if SIDE1_DEVICE in device_list:
                update_health("CAM1","OK")
                # update_cam_status("SIDE1_POST","YES")
                camlogger.critical("SIDE1 CAM is connected")
                print("SIDE1 CAM is connected")
            if SIDE2_DEVICE in device_list:
                update_health("CAM2","OK")
                # update_cam_status("SIDE2_POST","YES")
                camlogger.critical("SIDE2 CAM is connected")
                print("SIDE2 CAM is connected")
                
        # Initialize each camera
        #
        # *** NOTES ***
        # You may notice that the steps in this function have more loops with
        # less steps per loop; this contrasts the AcquireImages() function
        # which has less loops but more steps per loop. This is done for
        # demonstrative purposes as both work equally well.
        #
        # *** LATER ***
        # Each camera needs to be deinitialized once all images have been
        # acquired.
        for i, cam in enumerate(cam_list):

            # Initialize camera
            cam.Init()

        # Acquire images on all cameras
        result &= acquire_images(cam_list)

        # Deinitialize each camera
        #
        # *** NOTES ***
        # Again, each camera must be deinitialized separately by first
        # selecting the camera and then deinitializing it.
        for cam in cam_list:
            # Deinitialize camera
            cam.DeInit()
        # Release reference to camera
        # NOTE: Unlike the C++ examples, we cannot rely on pointer objects being automatically
        # cleaned up when going out of scope.
        # The usage of del is preferred to assigning the variable to None.
        del cam

    except PySpin.SpinnakerException as ex:
        print('Error: %s' % ex)
        result = False

    return result

def main():
    updateProcessId(processID)
    """
    Example entry point; please see Enumeration example for more in-depth
    comments on preparing and cleaning up the system.

    :return: True if successful, False otherwise.
    :rtype: bool
    """

    # Since this application saves images in the current folder
    # we must ensure that we have permission to write to this folder.
    # If we do not have permission, fail right away.
    try:
        test_file = open('test.txt', 'w+')
    except IOError:
        print('Unable to write to current directory. Please check permissions.')
        input('Press Enter to exit...')
        return False

    test_file.close()
    os.remove(test_file.name)

    result = True

    # Retrieve singleton reference to system object
    system = PySpin.System.GetInstance()

    # Get current library version
    version = system.GetLibraryVersion()
    print('Library version: %d.%d.%d.%d' % (version.major, version.minor, version.type, version.build))

    # Retrieve list of cameras from the system
    cam_list = system.GetCameras()

    num_cameras = cam_list.GetSize()

    print('Number of cameras detected: %d' % num_cameras)

    # Finish if there are no cameras
    if num_cameras == 0:
        update_health("CAM1","NOTOK")
        update_health("CAM2","NOTOK")
        # update_cam_status("SIDE1_POST","NO")
        # update_cam_status("SIDE2_POST","NO")

        # Clear camera list before releasing system
        cam_list.Clear()

        # Release system instance
        system.ReleaseInstance()

        print('Not enough cameras!')
        input('Done! Press Enter to exit...')
        return False

    # Run example on all cameras
    print('Running example for all cameras...')

    result = run_multiple_cameras(cam_list)

    print('Example complete... \n')

    # Clear camera list before releasing system
    cam_list.Clear()
    
    # Release system instance
    system.ReleaseInstance()

    input('Done! Press Enter to exit...')
    return result

if __name__ == '__main__':
    if main():
        sys.exit(0)
    else:
        sys.exit(1)
