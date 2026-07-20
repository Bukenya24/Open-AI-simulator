# ai simulator

# Garden Pest Deterrent System — AI Logic Simulation

Simulates the PIR sensor, ESP32-CAM capture, and dual-buzzer hardware in
software, while making REAL calls to the OpenAI API to identify a pest
species in a photo, then simulating the species-specific deterrent tone.

## The concept
1. PIR motion sensor detects movement in the garden
2. ESP32-CAM captures a photo of whatever triggered it
3. Photo is sent to OpenAI's vision model, which identifies the pest species:
   `bird`, `rodent`, `monkey`, `wildboar`, or `none`
4. The script looks up that species' deterrent profile and simulates the
   matching buzzer firing at the frequency/pattern known to scare it off:

   | Pest      | Frequency | Pattern              | Buzzer |
   |-----------|-----------|------------------------|--------|
   | Bird      | 3000 Hz   | 5x sharp 100ms pulses | HIGH |
   | Rodent    | 4500 Hz   | continuous 2s whine   | HIGH |
   | Monkey    | 800 Hz    | 4x loud 300ms bursts  | LOW  |
   | Wild boar | 300 Hz    | continuous 3s blast   | LOW  |

## Why two buzzers
Small, agile pests (birds, rodents) are deterred more effectively by sharp,
high-pitched tones; larger animals (monkeys, wild boar) respond better to
loud, low-pitched blasts. In the real hardware version, both buzzers are the
same piezo component — "high" and "low" just describe the frequency range
each one is driven at.

## Setup
```
pip install -r requirements.txt
export OPENAI_API_KEY=sk-proj-your-key-here
```

## Usage
Classify a single photo:
```
python security_system_sim.py --image your_photo.jpg
```

Loop-test against a folder of sample images, pressing Enter to simulate
each motion trigger:
```
python security_system_sim.py --interactive
```
(place a few `.jpg`/`.png` files — e.g. a bird, a rodent, a monkey, an empty
garden — in a `sample_images` folder next to the script first)

## Note on the frequencies
The values in `PEST_PROFILES` are a starting point, not measured pest
audiograms. Field-test against the actual pests in your garden and adjust
frequency, pulse pattern, and duration as needed — a cheap piezo buzzer
tops out well below true ultrasonic range, so "high frequency" here means
the highest pitch that buzzer can reliably produce, not literally
inaudible-to-humans.

## Security note
Never commit your API key to source control. Keep it as an environment
variable (as above) and make sure any `.env` file is listed in `.gitignore`.