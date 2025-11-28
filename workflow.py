import streamlit as st
import requests

# PAGE SETUP
st.set_page_config(page_title="Movie Workflow", layout="centered")

# ======================================================
# HUGGINGFACE INFERENCE API CALL (FREE)
# ======================================================
def hf_generate(prompt, model="tiiuae/falcon-7b-instruct", max_tokens=200):
    """
    Sends a text-generation request to HuggingFace API.
    You only need to supply HF_API_KEY in st.secrets.
    """
    headers = {"Authorization": f"Bearer {st.secrets['HF_API_KEY']}"}
    payload = {
        "inputs": prompt,
        "parameters": {"max_new_tokens": max_tokens}
    }
    url = f"https://api-inference.huggingface.co/models/{model}"

    r = requests.post(url, json=payload, headers=headers)
    r.raise_for_status()
    data = r.json()

    # HF sometimes returns a list with generated_text
    try:
        return data[0]["generated_text"]
    except:
        return str(data)

# ======================================================
# OMDb API CALL (FREE)
# ======================================================
def get_movie_data(title):
    """
    Returns data from OMDb.
    You only need to put OMDB_API_KEY into st.secrets.
    """
    key = st.secrets["OMDB_API_KEY"]
    url = f"http://www.omdbapi.com/?t={title}&apikey={key}&plot=full"
    r = requests.get(url)
    return r.json()

# ======================================================
# STREAMLIT UI
# ======================================================
st.title("🎬 Movie AI Workflow Demo")
st.write("A 4-Agent AI workflow using HuggingFace + OMDb (all free).")

movie_title = st.text_input("What is your favorite movie?")

if st.button("Run Workflow") and movie_title.strip():

    # --------------------------------------------------
    # AGENT A — Normalize Title
    # --------------------------------------------------
    st.write("### 🧩 Agent A — Normalizing Movie Title")
    normalized = hf_generate(
        f"Return only the properly capitalized movie title of: {movie_title}",
        max_tokens=20
    ).strip()
    st.write(f"Normalized Title: **{normalized}**")

    # --------------------------------------------------
    # AGENT B — OMDb Info + Poster
    # --------------------------------------------------
    st.write("### 🎞️ Agent B — Fetching Movie Metadata")
    info = get_movie_data(normalized)

    if info.get("Response") == "False":
        st.error("Movie not found. Try another movie name.")
        st.stop()

    # Poster
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
    # AGENT C — Generate AI Synopsis
    # --------------------------------------------------
    st.write("### 📖 Agent C — AI-Generated Synopsis")
    synopsis = hf_generate(
        f"Write a detailed movie synopsis for the film '{normalized}'.",
        max_tokens=250
    )
    st.write(synopsis)

    # --------------------------------------------------
    # AGENT D — Generate Quiz Questions
    # --------------------------------------------------
    st.write("### 📝 Agent D — Quiz Generator")
    quiz = hf_generate(
        f"Create 5 multiple-choice quiz questions based on this synopsis:\n{synopsis}",
        max_tokens=300
    )
    st.write(quiz)

    st.success("Workflow complete! 🎉")
