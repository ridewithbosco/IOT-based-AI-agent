import os
import warnings
import pyaudio
import wave
import audioop
from groq import Groq
import logging
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_best_microphone(audio):
    """Finds the best microphone dynamically (handles Pi/Linux ALSA issues)."""
    try:
        if os.name == 'nt':
            # On Windows, device 0 was previously working perfectly for your setup.
            return 0
            
        # On Raspberry Pi (Linux), ALSA defaults are messy. Look for a real mic.
        fallback_idx = None
        for i in range(audio.get_device_count()):
            dev_info = audio.get_device_info_by_index(i)
            name = dev_info.get('name', '').lower()
            channels = dev_info.get('maxInputChannels', 0)
            
            if channels > 0:
                if fallback_idx is None:
                    fallback_idx = i # Grab the first input device just in case
                if 'usb' in name or 'mic' in name:
                    return i
                    
        return fallback_idx if fallback_idx is not None else audio.get_default_input_device_info()['index']
    except Exception as e:
        logging.warning(f"Audio device detection failed: {e}")
        return None


def record_audio(file_path):
    # ==============================================
    # Audio Recording Configuration
    # ==============================================
    FORMAT = pyaudio.paInt16    # 16-bit integer samples
    CHANNELS = 1                # Mono audio
    RATE = 44100                # 44.1 kHz sampling
    CHUNK = 2048                # Frames per buffer
    
    # Silence detection settings
    SILENCE_THRESHOLD = 500     # RMS volume below this = silence (lower = more sensitive)
    SILENCE_DURATION = 2.0      # Seconds of silence before stopping (after speech detected)
    MIN_RECORDING_TIME = 1.0    # Minimum seconds to record before checking for silence
    MAX_WAIT_TIME = 15.0        # Maximum seconds to wait for speech before timeout
    
    audio = pyaudio.PyAudio()
    
    mic_index = get_best_microphone(audio)

    stream = audio.open(format=FORMAT,
                        channels=CHANNELS,
                        rate=RATE,
                        input=True,
                        input_device_index=mic_index,
                        frames_per_buffer=CHUNK)

    logging.info("Recording started... Speak something!")

    frames = []
    silent_chunks = 0
    speech_detected = False
    chunks_recorded = 0
    
    max_silent_chunks = int(SILENCE_DURATION * RATE / CHUNK)
    min_chunks_before_silence_check = int(MIN_RECORDING_TIME * RATE / CHUNK)
    max_wait_chunks = int(MAX_WAIT_TIME * RATE / CHUNK)

    while True:
        data = stream.read(CHUNK, exception_on_overflow=False)
        frames.append(data)
        chunks_recorded += 1

        rms = audioop.rms(data, 2)  # Measure volume
        
        # Detect if user has started speaking
        if rms >= SILENCE_THRESHOLD:
            speech_detected = True
            silent_chunks = 0  # Reset silence counter
        else:
            # Only count silence AFTER speech was detected AND minimum time passed
            if speech_detected and chunks_recorded > min_chunks_before_silence_check:
                silent_chunks += 1

        # Stop if: speech was detected AND silence duration reached
        if speech_detected and silent_chunks > max_silent_chunks:
            logging.info("Silence detected — stopping recording.")
            break
        
        # Timeout: stop if waiting too long for speech
        if not speech_detected and chunks_recorded >= max_wait_chunks:
            logging.info("No speech detected — timeout.")
            break

    stream.stop_stream()
    stream.close()
    audio.terminate()

 
    # Save Recorded File
    
    wf = wave.open(file_path, 'wb')
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(audio.get_sample_size(FORMAT))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    wf.close()

    logging.info(f"Saved as {file_path}")




# Transcription (Groq Whisper)

def transcribe_with_groq(file_path):
    client=Groq()
    stt_model="whisper-large-v3"
    audio_file=open(file_path, "rb")
    transcription=client.audio.transcriptions.create(
        model=stt_model,
        file=audio_file,
        language="en"
    )

    return transcription.text


# audio_filepath = "test_speech_to_text.mp3"
# record_audio(audio_filepath)
# print(transcribe_with_groq(audio_filepath))