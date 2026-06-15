"""App-wide constants."""

# RunLoop pump cadence (see ble/runloop.py)
PUMP_TICK_MS = 15
PUMP_SLICE_S = 0.005

# Collection timing
DEFAULT_PREP_TIME_S = 3.0          # PREP countdown before spelling
RAW_REFRESH_INTERVAL_S = 3.0       # re-arm raw mode every N seconds during a session

# UI
WINDOW_TITLE = "ASL Fingerspelling Collector"
WINDOW_MIN_SIZE = (920, 680)

# Channel target (15 = all 5 fingers; requires TapManager Developer Mode)
TARGET_ACCL_CHANNELS = 15
