import streamlit as st
import os
import base64
import time

st.set_page_config(page_title="Speech Data Curation", layout="centered")

st.title("🎤 Speech Data Curation App")
st.write("Click *Start Recording* → record your speech → click *Stop Recording* → save the audio.")

# Make folder
os.makedirs("recordings", exist_ok=True)

# HTML + JS widget
record_component = """
    <script>
    let mediaRecorder;
    let audioChunks = [];

    function startRecording() {
        navigator.mediaDevices.getUserMedia({ audio: true })
        .then(stream => {
            mediaRecorder = new MediaRecorder(stream);

            mediaRecorder.ondataavailable = e => {
                audioChunks.push(e.data);
            };

            mediaRecorder.onstop = () => {
                let blob = new Blob(audioChunks, { type: 'audio/webm' });
                audioChunks = [];

                let reader = new FileReader();
                reader.readAsDataURL(blob);
                reader.onloadend = () => {
                    let base64Data = reader.result;
                    window.parent.postMessage({ type: 'audio', data: base64Data }, "*");
                };
            };

            mediaRecorder.start();
        });
    }

    function stopRecording() {
        mediaRecorder.stop();
    }
    </script>

    <button onclick="startRecording()">🎙️ Start Recording</button>
    <button onclick="stopRecording()">⏹ Stop Recording</button>
"""

st.markdown(record_component, unsafe_allow_html=True)

# Receive data
data = st.experimental_get_query_params().get("audio_data", [None])[0]

# Use JS event listener for audio data
st.markdown("""
<script>
window.addEventListener("message", (event) => {
    if (event.data.type === "audio") {
        const queryString = window.location.search;
        const urlParams = new URLSearchParams(queryString);
        urlParams.set("audio_data", event.data.data);
        const newUrl = window.location.pathname + '?' + urlParams.toString();
        window.location.href = newUrl;
    }
});
</script>
""", unsafe_allow_html=True)


if data:
    st.success("Recording received!")

    # Decode base64
    header, encoded = data.split(",", 1)
    audio_bytes = base64.b64decode(encoded)

    st.audio(audio_bytes, format="audio/webm")

    filename = f"speech_{int(time.time())}.webm"
    filepath = f"recordings/{filename}"

    # Save
    with open(filepath, "wb") as f:
        f.write(audio_bytes)

    st.success(f"Saved as {filename}")

    st.download_button(
        label="⬇ Download Recording",
        data=audio_bytes,
        file_name=filename,
        mime="audio/webm",
    )
