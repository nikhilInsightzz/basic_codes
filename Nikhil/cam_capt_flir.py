import PySpin
import sys
import cv2
NUM_IMAGES = 100000000
savePath = "/home/ultratech-01/Downloads/IMAGES"
import shutil

class TriggerType:
    SOFTWARE = 1

CHOSEN_TRIGGER = TriggerType.SOFTWARE


def configure_trigger(cam):
    try:
        result = True
        if cam.TriggerMode.GetAccessMode() != PySpin.RW:
            print('Unable to disable trigger mode (node retrieval). Aborting...')
            return False

        cam.TriggerMode.SetValue(PySpin.TriggerMode_Off)

        print('Trigger mode disabled...')

        # Set TriggerSelector to FrameStart
        # For this example, the trigger selector should be set to frame start.
        # This is the default for most cameras.
        if cam.TriggerSelector.GetAccessMode() != PySpin.RW:
            print('Unable to get trigger selector (node retrieval). Aborting...')
            return False

        cam.TriggerSource.SetValue(PySpin.TriggerSelector_FrameStart)

        print('Trigger selector set to frame start...')

        if cam.TriggerSource.GetAccessMode() != PySpin.RW:
            print('Unable to get trigger source (node retrieval). Aborting...')
            return False

        if CHOSEN_TRIGGER == TriggerType.SOFTWARE:
            cam.TriggerSource.SetValue(PySpin.TriggerSource_Software)
            print('Trigger source set to software...')
        elif CHOSEN_TRIGGER == TriggerType.HARDWARE:
            cam.TriggerSource.SetValue(PySpin.TriggerSource_Line0)
            print('Trigger source set to hardware...')

        cam.TriggerMode.SetValue(PySpin.TriggerMode_On)
        print('Trigger mode turned back on...')

    except PySpin.SpinnakerException as ex:
        print('Error: %s' % ex)
        return False

    return result


def grab_next_image_by_trigger(cam):
    try:
        result = True
        if CHOSEN_TRIGGER == TriggerType.SOFTWARE:
            # Get user input
            

            # Execute software trigger
            if cam.TriggerSoftware.GetAccessMode() != PySpin.WO:
                print('Unable to execute trigger. Aborting...')
                return False

            cam.TriggerSoftware.Execute()

            # TODO: Blackfly and Flea3 GEV cameras need 2 second delay after software trigger

        elif CHOSEN_TRIGGER == TriggerType.HARDWARE:
            print('Use the hardware to trigger image acquisition.')

    except PySpin.SpinnakerException as ex:
        print('Error: %s' % ex)
        return False

    return result


def acquire_images(cam):
    print('*** IMAGE ACQUISITION ***\n')
    try:
        result = True

        # Set acquisition mode to continuous
        if cam.AcquisitionMode.GetAccessMode() != PySpin.RW:
            print('Unable to set acquisition mode to continuous. Aborting...')
            return False

        cam.AcquisitionMode.SetValue(PySpin.AcquisitionMode_Continuous)
        print('Acquisition mode set to continuous...')

        #  Begin acquiring images
        cam.BeginAcquisition()

        print('Acquiring images...')

        # Get device serial number for filename
        device_serial_number = ''
        if cam.TLDevice.DeviceSerialNumber.GetAccessMode() == PySpin.RO:
            device_serial_number = cam.TLDevice.DeviceSerialNumber.GetValue()

            print('Device serial number retrieved as %s...' % device_serial_number)

        processor = PySpin.ImageProcessor()
        processor.SetColorProcessing(PySpin.HQ_LINEAR)
        import time
        start=0
        savePath = "/home/nikhil/Downloads/Nikhil/"
        for i in range(NUM_IMAGES):
            try:
                
                #  Retrieve the next image from the trigger
                result &= grab_next_image_by_trigger(cam)

                #  Retrieve next received image
                image_result = cam.GetNextImage(100)
                

                #  Ensure image completion
                if image_result.IsIncomplete():
                    print('Image incomplete with image status %d ...' % image_result.GetImageStatus())

                else:

                    #  Print image information
                    width = image_result.GetWidth()
                    height = image_result.GetHeight()
                    print('Grabbed Image %d, width = %d, height = %d' % (i, width, height))

                    #  Convert image to mono 8
                    
                    image_converted = image_result.Convert(PySpin.PixelFormat_BGR8)
                    # width = image_result.GetWidth()
                    # height = image_result.GetHeight()
                    # rgb_array = image_converted.GetData()
                    # rgb_array = rgb_array.reshape(height, width, 3)
                    # image_nd = rgb_array
                    image_nd = image_converted.GetNDArray()

                    # Create a unique filename
                    if device_serial_number:
                        filename = savePath+'_tmp.jpg'
                    else:  # if serial number is empty
                        filename = savePath+'_tmp.jpg'

                    # Save image
                    # image_converted.Save(filename)
                    cv2.imwrite(filename, image_nd)
                    shutil.copy(filename, "/home/nikhil/Downloads/Nikhil/TMP/_tmp.jpg")


                    print('Image saved at %s\n' % filename)
                    print("total time : "+str((float(int(time.time())*10000)-start)))
                    start=int(time.time())*10000
                    #  Release image
                    image_result.Release()

            except PySpin.SpinnakerException as ex:
                acquire_images(cam)
                return False

        # End acquisition
        cam.EndAcquisition()

    except PySpin.SpinnakerException as ex:
        acquire_images(cam)
        return False

    return result


def reset_trigger(cam):
    try:
        result = True
        # Ensure trigger mode off
        # The trigger must be disabled in order to configure whether the source
        # is software or hardware.
        if cam.TriggerMode.GetAccessMode() != PySpin.RW:
            print('Unable to disable trigger mode (node retrieval). Aborting...')
            return False

        cam.TriggerMode.SetValue(PySpin.TriggerMode_Off)

        print('Trigger mode disabled...')

    except PySpin.SpinnakerException as ex:
        print('Error: %s' % ex)
        result = False

    return result


def print_device_info(nodemap):
    print('*** DEVICE INFORMATION ***\n')

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

    except PySpin.SpinnakerException as ex:
        print('Error: %s' % ex)
        return False

    return result


def run_single_camera(cam):
    try:
        result = True
        err = False

        # Retrieve TL device nodemap and print device information
        nodemap_tldevice = cam.GetTLDeviceNodeMap()

        result &= print_device_info(nodemap_tldevice)

        # Initialize camera
        cam.Init()

        # Retrieve GenICam nodemap
        nodemap = cam.GetNodeMap()

        # Configure trigger
        if configure_trigger(cam) is False:
            return False

        # Acquire images
        result &= acquire_images(cam)

        # Reset trigger
        result &= reset_trigger(cam)

        # Deinitialize camera
        cam.DeInit()

    except PySpin.SpinnakerException as ex:
        print('Error: %s' % ex)
        result = False

    return result


def main():
   
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
        # Clear camera list before releasing system
        cam_list.Clear()

        # Release system instance
        system.ReleaseInstance()

        print('Not enough cameras!')
        input('Done! Press Enter to exit...')
        return False
    savePath1 = "/home/ultratech-01/Downloads/IMAGES"
    # Run example on each camera
    for i, cam in enumerate(cam_list):

        print('Running example for camera %d...' % i)

        # result &= run_single_camera(cam,savePath1)
        result &= run_single_camera(cam)
        print('Camera %d example complete... \n' % i)

    # Release reference to camera
    # NOTE: Unlike the C++ examples, we cannot rely on pointer objects being automatically
    # cleaned up when going out of scope.
    # The usage of del is preferred to assigning the variable to None.
    del cam

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
