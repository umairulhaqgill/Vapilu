"""
VAD calibration - measures YOUR actual microphone levels so you can pick a
real threshold instead of guessing.

The default VAD_THRESHOLD of 500 was an estimate, not a measurement. Mic
sensitivity varies enormously between devices, so the right value for your
setup could easily be 200 or 3000.

Run:
    python calibrate_vad.py

It will ask you to stay quiet, then to talk, and print a recommended
threshold based on what it actually measured.
"""

import sys
import time

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
FRAME_MS = 20
FRAME_SAMPLES = int(SAMPLE_RATE * FRAME_MS / 1000)


def rms(frame_bytes: bytes) -> float:
    samples = np.frombuffer(frame_bytes, dtype=np.int16).astype(np.float32)
    if samples.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(samples ** 2)))


def measure(duration_seconds: float, label: str) -> list[float]:
    levels = []
    collected = {"frames": []}

    def callback(indata, frames, time_info, status):
        collected["frames"].append(bytes(indata))

    with sd.RawInputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16",
        blocksize=FRAME_SAMPLES,
        callback=callback,
    ):
        for remaining in range(int(duration_seconds), 0, -1):
            print(f"  {label}: {remaining}...  ", end="\r", flush=True)
            time.sleep(1)
    print(" " * 60, end="\r")

    for frame in collected["frames"]:
        levels.append(rms(frame))
    return levels


def main():
    print("VAD calibration\n")
    print("Step 1 of 2: stay SILENT (don't talk, normal room noise is fine).")
    input("Press Enter when ready, then stay quiet for 5 seconds...")
    silence = measure(5, "measuring silence")

    print("\nStep 2 of 2: TALK normally, like you would to the bot.")
    input("Press Enter when ready, then talk for 5 seconds...")
    speech = measure(5, "measuring speech")

    if not silence or not speech:
        print("Didn't capture any audio - is your microphone working?")
        sys.exit(1)

    silence_arr = np.array(silence)
    speech_arr = np.array(speech)

    # p95 of silence: how loud your background gets at its worst
    silence_p95 = float(np.percentile(silence_arr, 95))
    # p25 of speech: your quieter speech moments (want to still catch these)
    speech_p25 = float(np.percentile(speech_arr, 25))
    speech_median = float(np.median(speech_arr))

    print("\n--- Measurements ---")
    print(f"  Silence:  median {np.median(silence_arr):7.1f}   95th percentile {silence_p95:7.1f}")
    print(f"  Speech:   median {speech_median:7.1f}   25th percentile {speech_p25:7.1f}")

    if speech_p25 <= silence_p95:
        print("\nWARNING: your speech and background noise overlap heavily.")
        print("There's no threshold that cleanly separates them. Try:")
        print("  - moving the mic closer, or speaking louder")
        print("  - reducing background noise (fan, AC, open window)")
        print("  - checking you're using a headset mic, not a far-field laptop mic")
        recommended = silence_p95 * 2
    else:
        # Sit between the two, biased toward avoiding false triggers
        recommended = silence_p95 + (speech_p25 - silence_p95) * 0.4

    print(f"\n=== Recommended VAD_THRESHOLD: {int(recommended)} ===")
    print("\nPut this in your .env:")
    print(f"  VAD_THRESHOLD={int(recommended)}")
    print("\nIf it still triggers on noise, raise it. If it misses your")
    print("speech, lower it.")


if __name__ == "__main__":
    main()
