# RAVEN - AI Navigation Assistant

RAVEN is an interactive AI assistant that combines voice recognition, natural language processing, computer vision, and text-to-speech capabilities. It allows users to have natural conversations with an AI that can see through your PiCamera and respond intelligently to visual queries.

## Features

- 🎤 **Voice Interaction**: Speak naturally to the AI assistant
- 📹 **Computer Vision**: AI can see and analyze what's in front of your PiCamera
- 💬 **Conversational AI**: Powered by Google's Gemini model for natural responses
- 🎧 **Voice Output**: Responses are converted to speech using advanced TTS
- 🌐 **Web Interface**: Easy-to-use Gradio-based web interface with real-time PiCamera feed

## Prerequisites

- Python 3.8 or higher
- OpenCV-compatible PiCamera or webcam
- Internet connection for API calls

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/raven-ai-assistant.git
   cd raven-ai-assistant
   ```

2. Install `uv` if you don't have it already:
   ```bash
   pip install uv
   # or
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

3. Install dependencies using `uv`:
   ```bash
   uv sync
   ```

4. Set up environment variables:
   Create a `.env` file in the project root with the following:
   ```
   GROQ_API_KEY=your_groq_api_key_here
   GOOGLE_API_KEY=your_google_api_key_here
   ELEVENLABS_API_KEY=your_elevenlabs_api_key_here  # Optional, for better TTS
   ```

## Usage

Run the application using `uv`:
```bash
uv run main.py
```

Alternatively, you can run with Python directly after activating the virtual environment:
```bash
python main.py
```

The application will start a Gradio interface at `http://localhost:7860`. You can:
- Start/stop the PiCamera feed
- Allow continuous voice input
- Interact with the AI through voice or chat
- Ask questions that require visual analysis

## Project Structure

- `main.py`: Main application with Gradio interface and camera controls
- `ai_agent.py`: AI agent powered by Google's Gemini model
- `tools.py`: Computer vision tools for PiCamera image capture and analysis
- `speech_to_text.py`: Voice-to-text conversion functionality
- `text_to_speech.py`: Text-to-voice conversion
- `stt2.py`: Alternative speech-to-text implementation

## API Keys Required

To run this project, you'll need the following API keys:

### Google API Key (Required)
1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Generative Language API for your project
4. Navigate to "Credentials" in the left sidebar
5. Click "Create Credentials" and select "API Key"
6. Copy the generated API key and add it to your `.env` file as `GOOGLE_API_KEY`

### Groq API Key (Required)
1. Visit [Groq Cloud](https://console.groq.com/)
2. Sign up for an account or log in
3. Navigate to the "API Keys" section
4. Generate a new API key
5. Copy the key and add it to your `.env` file as `GROQ_API_KEY`

### ElevenLabs API Key (Optional)
1. Go to [ElevenLabs](https://elevenlabs.io/)
2. Sign up for an account or log in
3. Navigate to the "Profile" section
4. Find the "API Keys" section
5. Generate or copy your existing API key
6. Add it to your `.env` file as `ELEVENLABS_API_KEY`

### Setting Up Environment Variables
Create a `.env` file in your project root directory and add your API keys:

```
GROQ_API_KEY=your_groq_api_key_here
GOOGLE_API_KEY=your_google_api_key_here
ELEVENLABS_API_KEY=your_elevenlabs_api_key_here  # Optional
```

## How It Works

1. The application streams real-time video from your PiCamera
2. Voice input is captured and converted to text using Groq's speech recognition
3. The AI agent processes the query, potentially using the PiCamera image if needed
4. The response is converted back to speech and played aloud
5. The conversation history is maintained in the chat interface



## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Powered by Google's Gemini AI model
- Uses Gradio for the web interface
- Speech recognition powered by Groq
- Computer vision capabilities through OpenCV