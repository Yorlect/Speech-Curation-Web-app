import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode, ClientSettings
import av
import numpy as np
import wave
import time
import os

st.set_page_config(page_title="Speech Recorder", layout="centered")

st.title("🎤 Speech Recording App (Working Version)")
st.write("Press **Start** to begin and **Stop** to finish recording.")

# Folder to save recordings
os.makedirs("recordings", exist_ok=True)

# Buffer to store audio frames
audio_frames = []


def audio_callback(frame: av.AudioFrame):
    global audio_frames
    audio = frame.to_ndarray()
    audio_frames.append(audio)
    return frame


webrtc_streamer(
    key="speech-recorder",
    mode=WebRtcMode.SENDONLY,
    audio_receiver_size=1024,
    rtc_configuration={"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]},
    client_settings=ClientSettings(
        media_stream_constraints={"audio": True, "video": False}
    ),
    audio_frame_callback=audio_callback,
)

st.write("")

if st.button("💾 Save Recording"):
    if len(audio_frames) == 0:
        st.error("No audio recorded yet!")
    else:
        # Convert list to numpy array
        audio_np = np.concatenate(audio_frames, axis=1)

        # Create WAV file
        filename = f"recording_{int(time.time())}.wav"
        filepath = os.path.join("recordings", filename)

        with wave.open(filepath, "wb") as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(48000)
            f.writeframes(audio_np.tobytes())

        st.success(f"Recording saved as {filename}")

        # Provide download button
        with open(filepath, "rb") as f:
            audio_bytes = f.read()

        st.audio(audio_bytes, format="audio/wav")
        st.download_button(
            label="⬇ Download Recording",
            data=audio_bytes,
            file_name=filename,
            mime="audio/wav",
        )

        audio_frames.clear()
