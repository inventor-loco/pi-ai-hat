# Android App Client Build Instructions

The `android_client` folder contains a native Android application built in Kotlin. It acts as a mobile client for the Hailo-on-Pi server, providing an alternative to the web-based `index.html` interface with a native mobile experience.

## Prerequisites
- **Android Studio**: Download and install the latest version of [Android Studio](https://developer.android.com/studio).
- **Physical Android Device**: While you can use an emulator, testing the camera functionality is best done on a real physical device.

## Build and Run Steps

1. **Open Android Studio**.
2. From the welcome screen, click **Open** (or go to `File -> Open`).
3. Navigate to the `pi-ai-hat` workspace and select the `android_client` folder.
4. Android Studio will configure the project and sync Gradle dependencies (e.g., OkHttp). Wait for the sync to finish completely.
5. Enable **Developer Options** and **USB Debugging** on your Android device:
   - Go to `Settings -> About Phone` and tap `Build Number` 7 times.
   - Go back to `Settings -> System -> Developer Options` and enable `USB Debugging`.
6. Connect your Android device to your computer via USB. Ensure the device shows up in the device dropdown in the Android Studio toolbar.
7. Click the **Run** button (green play icon) or press `Shift + F10`.
8. The app will compile, install, and launch on your phone.

## Using the App
Once installed:
1. Ensure your phone is connected to the same local network (Wi-Fi) as the Raspberry Pi.
2. Launch the **Hailo Client** app.
3. Enter the URL of your Pi's server in the text field (e.g., `http://192.168.1.100:8000`).
4. Tap **Take Photo** to open your native camera app, take a picture, and tap the checkmark.
5. The image will be uploaded to the Pi, and the bounding boxes from the Hailo NPU inference will be drawn directly over the photo within the app!
