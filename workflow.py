import streamlit as st
import requests

st.set_page_config(page_title="Movie Workflow", layout="centered")

# ======================================================
# SAFE HUGGINGFACE CALL (Mistral — always available)
# ======================================================
def hf_generate(prompt, max_tokens=200):
    model = "mistralai/Mistral-7B-Instruct-v0.2"
    url = f"https://api-inference.huggingface.co/models/{model}"

    headers = {
        "Authorization": f"Bearer {st.secrets['HF_API_KEY']}",
        "Content-Type": "application/json"
    }

    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": max_tokens,
            "temperature": 0.7
        }
    }

    response = requests.post(url, headers=headers, json=payload)

    # Handle model loading state
    if response.status_code == 503:
        return "⚠️ Model is loading. Please click the button again."

    # Handle any other error
    if not response.ok:
        st.error(f"HuggingFace Error {response.status_code}: {response.text}")
        st.stop()

    try:
        data = response.json()
        return data[0]["generated_text"]
    except:
        return str(data)

# ======================================================
# OMDb API (Free)
# ======================================================
def get_movie_data(title):
    url = f"http://www.omdbapi.com/?t={title}&apikey={st.secrets['OMDB_API_KEY']}&plot=full"
    return requests.get(url).json()

# ======================================================
# UI
# ======================================================
st.title("🎬 Movie Workflow Demo — 4 AI Agents")
st.write("All free using HuggingFace + OMDb.")

movie_title = st.text_input("What is your favorite movie?")

if st.button("Run Workflow") and movie_title.strip():

    if "HF_API_KEY" not in st.secrets:
        st.error("Missing HuggingFace API key in secrets.")
        st.stop()

    if "OMDB_API_KEY" not in st.secrets:
        st.error("Missing OMDb API key in secrets.")
        st.stop()

    # --------------------------------------------------
    # AGENT A — Normalize Title
    # --------------------------------------------------
    st.write("### 🧩 Agent A — Normalize Title")
    normalized = hf_generate(
        f"Return only the correctly formatted movie title for: {movie_title}",
        max_tokens=30
    ).strip()
    st.write(f"**Normalized Title:** {normalized}")

    # --------------------------------------------------
    # AGENT B — Metadata + Poster
    # --------------------------------------------------
    st.write("### 🎞️ Agent B — Fetching Metadata")
    info = get_movie_data(normalized)

    if info.get("Response") == "False":
        st.error("Movie not found.")
        st.stop()

    if info.get("Poster") and info["Poster"] != "N/A":
        st.image(info["Poster"], width=300)

    st.json({
        "Title": info.get("Title"),
        "Year": info.get("Year"),
        "Genre": info.get("Genre"),
        "Director": info.get("Director"),
        "Actors": info.get("Actors"),
        "Plot": info.get("Plot")
    })

    # --------------------------------------------------
    # AGENT C — Synopsis
    # --------------------------------------------------
    st.write("### 📖 Agent C — AI Synopsis")
    synopsis = hf_generate(
        f"Write a detailed synopsis of the movie '{normalized}'.",
        max_tokens=250
    )
    st.write(synopsis)

    # --------------------------------------------------
    # AGENT D — Quiz
    # --------------------------------------------------
    st.write("### 📝 Agent D — Quiz Generator")
    quiz = hf_generate(
        f"Create 5 multiple-choice questions about the movie '{normalized}'. "
        f"Use this synopsis:\n{synopsis}",
        max_tokens=300
    )
    st.write(quiz)

    st.success("🎉 Workflow complete!")
