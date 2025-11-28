import streamlit as st
import requests
import random

# ---------------------------------------------------------
# PAGE CONFIG + CSS ANIMATIONS
# ---------------------------------------------------------
st.set_page_config(page_title="Movie Study Guide Generator", layout="wide")

# Fade-in animation and nicer layout
st.markdown("""
<style>
    .fade-in {
        animation: fadeIn 0.8s ease-in-out;
    }
    @keyframes fadeIn {
        from {opacity: 0;}
        to {opacity: 1;}
    }
    .title {
        font-size: 42px;
        font-weight: 700;
        margin-bottom: 10px;
    }
    .subtitle {
        font-size: 22px;
        margin-bottom: 30px;
    }
    .agent-box {
        padding: 20px;
        border-radius: 12px;
        background: #f5f5f5;
        margin-bottom: 20px;
        box-shadow: 0px 2px 6px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# HUGGINGFACE API HELPER
# ---------------------------------------------------------
HF_API_KEY = st.secrets["HF_TOKEN"]
HF_URL = "https://router.huggingface.co/v1/chat/completions"

def ask_huggingface(prompt):
    """Send prompt to llama model on HF Router."""
    payload = {
        "model": "meta-llama/Llama-3.1-8b-instruct",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 400
    }
    headers = {
        "Authorization": f"Bearer {HF_API_KEY}",
        "Content-Type": "application/json"
    }
    response = requests.post(HF_URL, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


# ---------------------------------------------------------
# OMDb API (Movie Data)
# ---------------------------------------------------------
OMDB_KEY = st.secrets["OMDB_KEY"]

def fetch_movie_data(title):
    url = f"http://www.omdbapi.com/?t={title}&apikey={OMDB_KEY}"
    data = requests.get(url).json()
    if data.get("Response") == "False":
        return None
    return data


# ---------------------------------------------------------
# UI — Title
# ---------------------------------------------------------
st.markdown('<div class="title fade-in">🎬 Movie Study Guide Workflow</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle fade-in">Enter a movie and generate a study guide, metadata, and a quiz.</div>', unsafe_allow_html=True)

movie = st.text_input("🎥 What is your favorite movie?", "")

if movie.strip():
    # ---------------------------------------------------------
    # AGENT A — Normalize Title
    # ---------------------------------------------------------
    with st.container():
        st.markdown("### 🟥 Agent A — Normalize Title")
        try:
            normalized_title = ask_huggingface(
                f"Normalize this movie title to its official capitalization: {movie}"
            )
        except:
            normalized_title = movie

        st.markdown(f"""
        <div class="agent-box fade-in">
        <b>Normalized Title:</b> {normalized_title}
        </div>
        """, unsafe_allow_html=True)

    # ---------------------------------------------------------
    # AGENT B — Metadata Paragraph (AI rewritten)
    # ---------------------------------------------------------
    with st.container():
        st.markdown("### 🟧 Agent B — Movie Metadata")

        movie_data = fetch_movie_data(normalized_title)

        if movie_data:
            # Show poster if available
            poster_url = movie_data.get("Poster", "")
            col1, col2 = st.columns([1, 2])

            with col1:
                if poster_url and poster_url != "N/A":
                    st.image(poster_url, width=280)

            # Create an AI-styled metadata paragraph
            meta_text = ask_huggingface(
                f"Rewrite the following movie info as a single smooth descriptive paragraph "
                f"that feels like high-quality study guide material:\n\n{movie_data}"
            )

            with col2:
                st.markdown(f"""
                <div class="agent-box fade-in">
                {meta_text}
                </div>
                """, unsafe_allow_html=True)

        else:
            st.error("Movie not found in OMDb. Check your OMDb key or the movie title.")


    # ---------------------------------------------------------
    # AGENT C — Study Guide Summary
    # ---------------------------------------------------------
    with st.container():
        st.markdown("### 🟨 Agent C — Study Guide Summary")

        summary = ask_huggingface(
            f"Create a study-friendly summary of the movie '{normalized_title}' "
            f"based on typical themes, plot points, director style, and cultural impact. "
            f"Write as if preparing material for a film class."
        )

        st.markdown(f"""
        <div class="agent-box fade-in">
        {summary}
        </div>
        """, unsafe_allow_html=True)


    # ---------------------------------------------------------
    # AGENT D — Quiz Generator (linked to summary)
    # ---------------------------------------------------------
    st.markdown("### 🟩 Agent D — Quiz")

    # Generate quiz from the summary
    quiz_data = ask_huggingface(
        f"Based ONLY on the following text, generate a 5-question multiple choice quiz. "
        f"Each question must include:\n"
        f"- The question\n"
        f"- 4 answer options (A, B, C, D)\n"
        f"- The correct answer letter\n"
        f"- A one-sentence explanation\n\n"
        f"TEXT:\n{summary}"
    )

    # Store quiz persistently
    if "quiz" not in st.session_state:
        st.session_state.quiz = quiz_data

    st.markdown(f"""
    <div class="agent-box fade-in">
    {st.session_state.quiz}
    </div>
    """)

    st.info("✨ The quiz stays on screen without resetting other agents.")

