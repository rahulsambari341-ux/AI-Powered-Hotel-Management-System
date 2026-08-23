from kokoro import KPipeline
import soundfile as sf

print("Loading Kokoro...")

pipeline = KPipeline(lang_code="a")

text = "Hello Rahul. Welcome to our AI Hotel Booking Agent. Your Deluxe room has been booked successfully."

print("Generating speech...")

generator = pipeline(
    text,
    voice="af_heart",
    speed=1.0,
    split_pattern=r"\n+"
)

for i, (gs, ps, audio) in enumerate(generator):
    filename = f"kokoro_test_{i}.wav"
    sf.write(filename, audio, 24000)

    print(f"Generated: {filename}")
    print(f"Text: {gs}")

print("Kokoro TTS test completed successfully!")