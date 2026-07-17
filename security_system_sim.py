"""
Garden Pest Deterrent System — AI Logic Simulation
-----------------------------------------------------
Simulates the PIR sensor, ESP32-CAM capture, and dual-buzzer hardware in
software, while making REAL calls to the OpenAI API to identify a pest
species in a photo, then simulating the species-specific deterrent tone.

Use this to test/tune your AI prompt and frequency table before flashing
firmware to real hardware.

Usage:
    export OPENAI_API_KEY="sk-..."
    python security_system_sim.py --image path/to/photo.jpg
    python security_system_sim.py --interactive   # press Enter to simulate PIR triggers,
                                                    # cycles through images in ./sample_images/

Requires:
    pip install -r requirements.txt
"""

import argparse
import base64
import os
import sys
import time
import glob
import logging
from dataclasses import dataclass, field
from typing import Optional

from openai import OpenAI

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("pest_deterrent")

MODEL = "gpt-4o-mini"
COOLDOWN_SECONDS = 5

# ---- Pest -> deterrent profile lookup table -----------------------------
# Frequencies are a starting point, not measured acoustics. Piezo buzzers
# can't reach true ultrasonic range, so "high" here means the highest
# practical pitch a cheap piezo disc reliably reproduces. Tune these
# against what actually scares off the pests in your garden.
@dataclass
class PestProfile:
    frequency_hz: int
    pattern: str          # human-readable description used in the log
    buzzer: str            # "high" or "low"
    pulses: Optional[list] = None  # list of (on_ms, off_ms) if pulsed
    duration_ms: int = 0            # used if pulses is None (continuous tone)


PEST_PROFILES = {
    "bird":     PestProfile(3000, "5x sharp 100ms pulses", "high", pulses=[(100, 100)] * 5),
    "rodent":   PestProfile(4500, "continuous 2s whine",    "high", duration_ms=2000),
    "monkey":   PestProfile(800,  "4x loud 300ms bursts",   "low",  pulses=[(300, 200)] * 4),
    "wildboar": PestProfile(300,  "continuous 3s blast",    "low",  duration_ms=3000),
}
VALID_LABELS = set(PEST_PROFILES.keys()) | {"none"}


@dataclass
class ClassificationResult:
    label: str
    raw_response: str


class MotionSensor:
    """Mocks a PIR sensor. In interactive mode, a keypress = motion event."""

    def trigger(self) -> bool:
        input("\n>> Press ENTER to simulate motion in the garden (Ctrl+C to quit)... ")
        return True


class Camera:
    """Mocks the ESP32-CAM: 'captures' by loading a local image file."""

    def __init__(self, image_path: str):
        if not os.path.isfile(image_path):
            raise FileNotFoundError(f"Image not found: {image_path}")
        self.image_path = image_path

    def capture(self) -> bytes:
        log.info(f"[CAM] Capturing frame from {os.path.basename(self.image_path)}")
        with open(self.image_path, "rb") as f:
            return f.read()


class AIAnalyzer:
    """Sends the captured frame to OpenAI's vision-capable model to identify the pest."""

    PROMPT = (
        "You are a garden pest-camera AI. Identify the main subject of this "
        "frame as exactly one word from this list: bird, rodent, monkey, "
        "wildboar, none (none = empty scene / no clear pest). "
        "Reply with only that single word, nothing else."
    )

    def __init__(self, client: OpenAI):
        self.client = client

    def classify(self, image_bytes: bytes) -> ClassificationResult:
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        log.info("[AI] Sending frame to OpenAI for pest identification...")

        response = self.client.chat.completions.create(
            model=MODEL,
            max_tokens=5,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": self.PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                        },
                    ],
                }
            ],
        )

        raw = response.choices[0].message.content.strip().lower()
        label = next((v for v in VALID_LABELS if v in raw), "none")
        return ClassificationResult(label=label, raw_response=raw)


class BuzzerController:
    """Simulates two frequency-tuned buzzers with console output (no real hardware needed)."""

    def deter(self, pest: str, profile: PestProfile):
        buzzer_name = "HIGH-freq buzzer" if profile.buzzer == "high" else "LOW-freq buzzer"
        log.warning(
            f"[BUZZ] {pest.upper()} detected -> {buzzer_name} @ {profile.frequency_hz} Hz "
            f"({profile.pattern})"
        )
        if profile.pulses:
            for on_ms, off_ms in profile.pulses:
                log.info(f"        tone({profile.frequency_hz}Hz) for {on_ms}ms, silence {off_ms}ms")
        else:
            log.info(f"        tone({profile.frequency_hz}Hz) held for {profile.duration_ms}ms")

    def silent(self):
        log.info("[BUZZ] No recognised pest — buzzers stay silent")


class PestDeterrentSystem:
    def __init__(self, client: OpenAI):
        self.motion_sensor = MotionSensor()
        self.analyzer = AIAnalyzer(client)
        self.buzzer = BuzzerController()
        self.last_trigger = 0.0

    def process_image(self, image_path: str):
        camera = Camera(image_path)
        frame = camera.capture()
        result = self.analyzer.classify(frame)
        log.info(f"[AI] Identified: {result.label} (raw: '{result.raw_response}')")
        self._act_on(result.label)

    def _act_on(self, label: str):
        profile = PEST_PROFILES.get(label)
        if profile:
            self.buzzer.deter(label, profile)
        else:
            self.buzzer.silent()

    def run_interactive(self, sample_dir: str):
        images = sorted(glob.glob(os.path.join(sample_dir, "*")))
        images = [f for f in images if f.lower().endswith((".jpg", ".jpeg", ".png"))]
        if not images:
            log.error(f"No images found in {sample_dir}. Add some .jpg/.png files there.")
            sys.exit(1)

        idx = 0
        log.info("System armed. Watching the garden...")
        try:
            while True:
                now = time.time()
                if now - self.last_trigger < COOLDOWN_SECONDS:
                    remaining = COOLDOWN_SECONDS - (now - self.last_trigger)
                    log.info(f"[SYS] Cooling down ({remaining:.1f}s left)...")
                    time.sleep(remaining)

                self.motion_sensor.trigger()
                log.info("[PIR] Motion detected!")
                self.last_trigger = time.time()

                image_path = images[idx % len(images)]
                idx += 1
                self.process_image(image_path)
        except KeyboardInterrupt:
            log.info("\nSystem disarmed. Goodbye.")


def main():
    parser = argparse.ArgumentParser(description="Garden Pest Deterrent System — AI simulation")
    parser.add_argument("--image", help="Path to a single image to classify once")
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Loop: press Enter to simulate a PIR trigger, cycling through ./sample_images/",
    )
    parser.add_argument(
        "--sample-dir",
        default=os.path.join(os.path.dirname(__file__), "sample_images"),
        help="Directory of images to cycle through in --interactive mode",
    )
    args = parser.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        log.error("OPENAI_API_KEY not set. Run: export OPENAI_API_KEY='sk-...'")
        sys.exit(1)

    client = OpenAI(api_key=api_key)
    system = PestDeterrentSystem(client)

    if args.image:
        system.process_image(args.image)
    elif args.interactive:
        system.run_interactive(args.sample_dir)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

