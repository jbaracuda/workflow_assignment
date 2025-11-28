import streamlit as st
import requests
import random

# ---------------------------------------------------------
# PAGE CONFIG + CSS ANIMATIONS
# ---------------------------------------------------------
st.set_page_config(page_title="Movie Study Guide Generator", layout="wide")

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
# OPENROUTER API CALL
# ---------------------------------------------------------
OPENROUTER_KEY = st.secrets["OPENROUTER_API_KEY"]

def ask_openrouter(prompt):
    """
    Sends prompt to OpenRouter using a LLaMA model.
    """
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "meta-llama/llama-3.1-70b-instruct",  
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 400
    }

    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


# ---------------------------------------------------------
# OMDb API (Movie Database)
# ---------------------------------------------------------
OMDB_KEY = st.secrets["OMDB_KEY"]

def fetch_movie_data(title):
    url = f"http://www.omdbapi.com/?t={title}&apikey={OMDB_KEY}"
    data = requests.get(url).json()
    if data.get("Response") == "False":
        return None
    return data


# ---------------------------------------------------------
# UI Header
# ---------------------------------------------------------
st.markdown('<div class="title fade-in">🎬 Movie Study Guide Workflow</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle fade-in">Enter a movie and generate a study guide, metadata, and a quiz.</div>', unsafe_allow_html=True)

movie = st.text_input("🎥 What is your favorite movie?")

# ---------------------------------------------------------
# RUN WORKFLOW
# ---------------------------------------------------------
if movie.strip():

    # -----------------------------------------
    # Agent A — Normalize Title
    # -----------------------------------------
    st.markdown("### 🟥 Agent A — Normalize Title")

    try:
        normalized_title = ask_openrouter(
            f"Normalize this movie title to its official capitalization: {movie}"
        )
    except:
        normalized_title = movie

    st.markdown(f"""
    <div class="agent-box fade-in">
        <b>Normalized Title:</b> {normalized_title}
    </div>
    """, unsafe_allow_html=True)

    # -----------------------------------------
    # Agent B — AI-Rewritten Metadata
    # -----------------------------------------
    st.markdown("### 🟧 Agent B — Movie Metadata")

    movie_data = fetch_movie_data(normalized_title)

    if movie_data:
        poster_url = movie_data.get("Poster", "")

        col1, col2 = st.columns([1, 2])

        with col1:
            if poster_url != "N/A" and poster_url:
                st.image(poster_url, width=280)

        # Rewrite metadata into a smooth paragraph
        meta_paragraph = ask_openrouter(
            f"Rewrite the following movie information as one smooth, educational paragraph "
            f"suitable for a study guide.\n\n{movie_data}"
        )

        with col2:
            st.markdown(f"""
            <div class="agent-box fade-in">{meta_paragraph}</div>
            """, unsafe_allow_html=True)

    else:
        st.error("Movie not found in OMDb. Check your movie title or OMDb key.")

    # -----------------------------------------
    # Agent C — Study Guide Summary
    # -----------------------------------------
    st.markdown("### 🟨 Agent C — Study Guide Summary")

    summary = ask_openrouter(
        f"Write a study-friendly summary explaining the key plot, themes, stylistic elements, "
        f"and cultural significance of the movie '{normalized_title}'. "
        f"Write it like material for a film analysis class."
    )

    st.markdown(f"""
    <div class="agent-box fade-in">{summary}</div>
    """, unsafe_allow_html=True)

    # -----------------------------------------
    # Agent D — Quiz (using summary)
    # -----------------------------------------
    st.markdown("### 🟩 Agent D — Quiz")

    # Generate quiz from the summary
    quiz = ask_openrouter(
        f"Using ONLY this study guide text, generate a 5-question multiple choice quiz. "
        f"Each question must include:\n"
        f"- The question\n"
        f"- Four answer choices labeled A, B, C, D\n"
        f"- The correct answer letter\n"
        f"- A one-sentence explanation\n\n"
        f"TEXT:\n{summary}"
    )

    # Persist quiz so UI doesn't reset
    if "quiz" not in st.session_state:
        st.session_state.quiz = quiz

    st.markdown(f"""
    <div class="agent-box fade-in">{st.session_state.quiz}</div>
    """, unsafe_allow_html=True)

    st.success("✨ Agents will stay visible when selecting answers.")


