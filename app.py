import streamlit as st
from streamlit_js_eval import streamlit_js_eval
import base64
import time

st.set_page_config(page_title="Speech Recorder", layout="centered")

st.title("🎤 Speech Recording Web App")
st.write("Click the button below to start and stop recording.")

# --- AUDIO RECORDING USING JAVASCRIPT ---
record = streamlit_js_eval(
    js_expressions="""
    var recordAudio = async () => {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const mediaRecorder = new MediaRecorder(stream);
        let chunks = [];

        mediaRecorder.ondataavailable = e => chunks.push(e.data);

        mediaRecorder.onstop = e => {
            let blob = new Blob(chunks, { type: 'audio/webm' });
            let reader = new FileReader();
            reader.readAsDataURL(blob);
            reader.onloadend = () => {
                let base64data = reader.result;
                window.parent.postMessage({type:'AUDIO_DATA', data: base64data}, '*');
            };
        };

        window.mediaRecorder = mediaRecorder;
        mediaRecorder.start();
    };

    var stopRecording = () => {
        window.mediaRecorder.stop();
    };

    """,
    key="init"
)

# Start/Stop buttons
col1, col2 = st.columns(2)
with col1:
    start_btn = st.button("🎙️ Start Recording")
with col2:
    stop_btn = st.button("⏹ Stop Recording")

if start_btn:
    streamlit_js_eval(js_expressions="recordAudio();", key="start")

if stop_btn:
    streamlit_js_eval(js_expressions="stopRecording();", key="stop")

# --- RECEIVING AUDIO BACK FROM JS ---
audio_data = streamlit_js_eval(
    js_expressions="window.recordedAudioData",
    key="receive_audio"
)

if audio_data:
    st.success("Recording complete!")

    # Extract Base64 audio
    header, encoded = audio_data.split(",", 1)
    audio_bytes = base64.b64decode(encoded)

    st.audio(audio_bytes, format="audio/webm")

    # Save file with timestamp
    filename = f"recording_{int(time.time())}.webm"

    # Download button
    st.download_button(
        label="⬇ Download Recording",
        data=audio_bytes,
        file_name=filename,
        mime="audio/webm"
    )

    # Save to server folder
    with open(filename, "wb") as f:
        f.write(audio_bytes)

    st.info(f"Saved as `{filename}` on server.")
