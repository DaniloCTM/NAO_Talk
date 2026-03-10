import sounddevice as sd
import numpy as np
import queue
import webrtcvad
import collections
import sys
from faster_whisper import WhisperModel

# =====================
# CONFIG
# =====================
MODEL_SIZE = "small"
SAMPLE_RATE = 16000
FRAME_DURATION = 30  # ms (10, 20 ou 30)
VAD_AGGRESSIVENESS = 2

# =====================
# MODEL
# =====================
print("Carregando modelo...")
model = WhisperModel(MODEL_SIZE, device="auto", compute_type="int8")
print("Modelo carregado.")

# =====================
# AUDIO
# =====================
audio_queue = queue.Queue()
vad = webrtcvad.Vad(VAD_AGGRESSIVENESS)

def audio_callback(indata, frames, time, status):
    audio_queue.put(bytes(indata))

def frame_generator():
    frame_size = int(SAMPLE_RATE * FRAME_DURATION / 1000) * 2
    while True:
        data = audio_queue.get()
        for i in range(0, len(data), frame_size):
            yield data[i:i+frame_size]

def vad_collector():
    ring_buffer = collections.deque(maxlen=10)
    triggered = False
    voiced_frames = []

    for frame in frame_generator():
        if len(frame) < 640:
            continue

        is_speech = vad.is_speech(frame, SAMPLE_RATE)

        if not triggered:
            ring_buffer.append((frame, is_speech))
            num_voiced = len([f for f, speech in ring_buffer if speech])
            if num_voiced > 0.8 * ring_buffer.maxlen:
                triggered = True
                voiced_frames.extend(f for f, s in ring_buffer)
                ring_buffer.clear()
        else:
            voiced_frames.append(frame)
            ring_buffer.append((frame, is_speech))
            num_unvoiced = len([f for f, speech in ring_buffer if not speech])
            if num_unvoiced > 0.8 * ring_buffer.maxlen:
                triggered = False
                yield b''.join(voiced_frames)
                ring_buffer.clear()
                voiced_frames = []

print("Escutando...")

with sd.RawInputStream(
    samplerate=SAMPLE_RATE,
    blocksize=int(SAMPLE_RATE * FRAME_DURATION / 1000),
    dtype="int16",
    channels=1,
    callback=audio_callback,
):
    for speech in vad_collector():
        audio_np = np.frombuffer(speech, np.int16).astype(np.float32) / 32768.0
        segments, _ = model.transcribe(audio_np, language="pt", beam_size=1)

        print("\n🗣 Transcrição:")
        for segment in segments:
            print(segment.text)
