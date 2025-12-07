import streamlit as st
from audio_recorder_streamlit import audio_recorder
import time
import os

st.set_page_config(page_title="Speech Data Curation")

st.title("🎤 Speech Data Curation App")
st.write("Click the microphone icon to record speech.")

# ensure output folder exists
os.makedirs("recordings", exist_ok=True)

# UI: Microphone widget
audio_bytes = audio_recorder(
    text="Click to record",
    recording_color="#FF3333",
    neutral_color="#6aa36f",
    icon_name="microphone",
    icon_size="3x",
)

# When recording is ready
if audio_bytes:
    st.success("Recording received!")

    # playback
    st.audio(audio_bytes, format="audio/wav")

    # save file
    filename = f"recording_{int(time.time())}.wav"
    filepath = f"recordings/{filename}"

    with open(filepath, "wb") as f:
        f.write(audio_bytes)

    st.success(f"Saved as {filename}")

    # download
    st.download_button(
        "⬇ Download audio",
        audio_bytes,
        file_name=filename,
        mime="audio/wav",
    )
