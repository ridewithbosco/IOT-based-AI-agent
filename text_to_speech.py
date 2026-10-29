import os
import elevenlabs
from elevenlabs.client import ElevenLabs
import pygame
from gtts import gTTS

ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")

# ------------------------------
# INTERNAL MP3 PLAYER (No UI)
# ------------------------------
def play_audio(output_filepath):
    """Play audio file."""
    try:
        pygame.mixer.init()
        pygame.mixer.music.load(output_filepath)
        pygame.mixer.music.play()

        # Wait until playback finishes
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)

        # Release file lock
        pygame.mixer.music.unload()
        pygame.mixer.quit()
    
    except Exception as e:
        print(f"Error playing audio: {e}")


# ------------------------------
# ELEVENLABS TTS
# ------------------------------
def text_to_speech_with_elevenlabs(input_text, output_filepath):
    client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
    
    audio = client.text_to_speech.convert(
        text=input_text,
        voice_id="ZF6FPAbjXT4488VcRRnw",
        model_id="eleven_multilingual_v2",
        output_format="mp3_22050_32",
    )
    
    elevenlabs.save(audio, output_filepath)
    play_audio(output_filepath)


# ------------------------------
# GOOGLE GTTS (Faster Speech)
# ------------------------------
def text_to_speech_with_gtts(input_text, output_filepath):
    """
    Text to speech using gTTS with faster speech.
    
    Using tld='co.uk' produces slightly faster speech.
    Using tld='com.au' or 'co.in' can also vary speed.
    """
    # Use UK English which tends to speak faster
    tts = gTTS(text=input_text, lang="en", tld="co.uk", slow=False)
    tts.save(output_filepath)
    play_audio(output_filepath)


# ------------------------------
# TEST
# ------------------------------
# text_to_speech_with_gtts("Hello, this is a test of faster speech output.", "final.mp3")


