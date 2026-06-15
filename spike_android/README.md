# TapStrap MTU Spike (Android)

A throw-away Android app that answers **one** question:

> Does Android receive 15-channel accelerometer data from Tap Strap 2,
> or is it still truncated to 8 channels like on macOS?

If the answer is "15 channels" then the `finger/tapstrap/SENSOR_FORMAT.md`
note saying "TapStrap 2 BLE MTU fixed at 23 bytes, cannot negotiate larger"
is wrong — the limit is macOS CoreBluetooth, not Tap Strap firmware.
That unlocks the full 5-finger sensing path for the INFOCOM 2027 paper.

## Critical fact: emulator cannot test BLE

Android emulators have no real Bluetooth radio. **You must run this on a
real phone.** Any phone with Android 8.0+ and Bluetooth LE works.

## How to run

1. **Open in Android Studio**
   `File → Open → /Users/houzhen/research/paper_infocom_2027/spike_android`
   Android Studio will sync Gradle on first open; click "OK" when prompted.

2. **Plug in an Android phone via USB**
   On the phone: Settings → About → tap "Build number" 7 times to enable
   Developer Options, then Settings → Developer Options → enable
   "USB debugging".

3. **Click the green Run ▶ button**
   Android Studio will install the app on the phone (~30s the first time).

4. **Allow Bluetooth permissions** when the app prompts.

5. **Wake the Tap Strap** by tapping fingers against a surface so the LED
   pulses (it goes to sleep after idle).

6. **In the app, press "Scan & Connect"**

## What to look at

The green metrics panel at the top shows the three numbers that decide
everything:

| Metric                  | Bad (current Mac state) | Good (spike succeeds) |
|-------------------------|-------------------------|-----------------------|
| MTU                     | 23                      | ≥ 37 (likely 247)     |
| Max packet size seen    | ≤ 23 bytes              | > 23 bytes            |
| Max accl channels seen  | 8                       | 15                    |

**"Max accl channels seen = 15"** is the win condition. Anything less
means firmware really does limit Tap Strap to 8 channels regardless of
the host BLE stack, and the INFOCOM paper needs to plan around that.

## Logs to grab

After running for ~30 seconds with Tap Strap connected:

1. Screenshot the green metrics panel.
2. Screenshot the live log.
3. Optional: `adb logcat -s TapStrap` and save 1 minute of output.

Send those back; that's the experimental record for this decision.

## File layout

```
spike_android/
├── README.md                 (this file)
├── settings.gradle
├── build.gradle              (project)
├── gradle.properties
├── gradle/wrapper/gradle-wrapper.properties
└── app/
    ├── build.gradle          (app module)
    └── src/main/
        ├── AndroidManifest.xml
        ├── res/
        │   ├── layout/activity_main.xml
        │   └── values/{strings,themes}.xml
        └── java/com/research/tapstrapspike/
            ├── MainActivity.kt       # UI + permissions
            ├── TapStrapClient.kt     # BLE flow + MTU request
            └── RawParser.kt          # raw-mode packet parser
                                       # (port of finger/tapstrap parse_raw)
```

## After the spike

Whichever way it goes, this code becomes the seed of the full
collection app (the BLE client and parser are 100% reusable). The
next layer (prompts, video, session storage) lives in the same
project, added on top.
