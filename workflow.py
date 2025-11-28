import streamlit as st
import requests
import json

st.set_page_config(page_title="Movie Workflow", layout="centered")

# =========================
# Session State Setup
# =========================
for key in [
    "normalized_title",
    "metadata_paragraph",
    "metadata_poster",
    "synopsis",
    "quiz_data",
    "user_answers",
    "show_results",
]:
    if key not in st.session_state:
        st.session_state[key] = None


# =========================
# OpenRouter / LLaMA Generator
# =========================
def llama_generate(prompt, max_tokens=250):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {st.secrets['OPENROUTER_API_KEY']}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "meta-llama/llama-3-8b-instruct",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
    }

    response = requests.post(url, json=payload, headers=headers)

    if not response.ok:
        st.error(f"OpenRouter Error {response.status_code}: {response.text}")
        st.stop()

    data = response.json()
    return data["choices"][0]["message"]["content"]


# =========================
# OMDb Metadata Fetcher
# =========================
def get_movie_data(title):
    url = f"http://www.omdbapi.com/?t={title}&apikey={st.secrets['OMDB_API_KEY']}&plot=full"
    return requests.get(url).json()


# =========================
# Quiz Parser
# =========================
def parse_quiz(text):
    """
    Expected Quiz Format:
    Q1: ...
    A) ...
    B) ...
    C) ...
    D) ...
    Answer: X
    Explanation: ...
    """
    questions = []
    blocks = text.split("Q")
    for block in blocks[1:]:
        lines = block.strip().split("\n")
        question_line = lines[0][3:].strip()  # skip "1: "
        choices = [l[3:].strip() for l in lines[1:5]]  # remove "A) "
        answer_line = next(l for l in lines if l.startswith("Answer"))
        explanation_line = next(l for l in lines if l.startswith("Explanation"))

        answer = answer_line.split(":")[1].strip()
        explanation = explanation_line.split(":")[1].strip()

        questions.append(
            {
                "question": question_line,
                "choices": choices,
                "answer": answer,
                "explanation": explanation,
            }
        )
    return questions


# ============================================================
# UI Title
# ============================================================
st.title("🎬 Movie Workflow — 4-Agent AI System")


# =========================
# Input
# =========================
movie_title = st.text_input("What is your favorite movie?")


# =========================
# Run Workflow Button
# =========================
if st.button("Run Workflow") and movie_title.strip():

    # Reset quiz state
    st.session_state.quiz_data = None
    st.session_state.user_answers = {}
    st.session_state.show_results = False

    # -------------------------
    # AGENT A — Normalize Title
    -------------------------
    normalized = llama_generate(
        f"Return only the correctly formatted official movie title: {movie_title}",
        max_tokens=20,
    ).strip()

    st.session_state.normalized_title = normalized

    # -------------------------
    # AGENT B — Movie Background
    -------------------------
    raw_info = get_movie_data(normalized)

    if raw_info.get("Response") == "False":
        st.error("Movie not found in OMDb.")
        st.stop()

    st.session_state.metadata_poster = (
        raw_info.get("Poster") if raw_info.get("Poster") != "N/A" else None
    )

    metadata_prompt = f"""
Write a polished paragraph describing key background details about the movie '{normalized}'.
Include the release year, genre, director, major cast members, and general significance.
Here is the data:

Title: {raw_info.get("Title")}
Year: {raw_info.get("Year")}
Genre: {raw_info.get("Genre")}
Director: {raw_info.get("Director")}
Actors: {raw_info.get("Actors")}
Plot: {raw_info.get("Plot")}
"""

    st.session_state.metadata_paragraph = llama_generate(
        metadata_prompt, max_tokens=180
    )

    # -------------------------
    # AGENT C — Synopsis
    -------------------------
    st.session_state.synopsis = llama_generate(
        f"Write a rich, detailed synopsis of the movie '{normalized}'.",
        max_tokens=300,
    )

    # -------------------------
    # AGENT D — Quiz
    -------------------------
    quiz_prompt = f"""
Using ONLY the synopsis below, create a 5-question multiple-choice quiz.

Format EXACTLY like this:

Q1: What is the question?
A) Option A
B) Option B
C) Option C
D) Option D
Answer: A
Explanation: Explanation text.

SYNOPSIS:
{st.session_state.synopsis}
"""

    raw_quiz = llama_generate(quiz_prompt, max_tokens=350)
    st.session_state.quiz_data = parse_quiz(raw_quiz)


# ============================================================
# ALWAYS SHOW AGENTS A–C IF AVAILABLE
# ============================================================
if st.session_state.normalized_title:
    st.header("Agent A — Title Normalization")
    st.success(st.session_state.normalized_title)

if st.session_state.metadata_paragraph:
    st.header("Agent B — Background")

    if st.session_state.metadata_poster:
        st.image(st.session_state.metadata_poster, width=300)

    st.write(st.session_state.metadata_paragraph)

if st.session_state.synopsis:
    st.header("Agent C — Synopsis")
    st.write(st.session_state.synopsis)


# ============================================================
# QUIZ (AGENT D)
# ============================================================
if st.session_state.quiz_data:

    st.header("Agent D — Movie Quiz")

    # Show questions
    for i, q in enumerate(st.session_state.quiz_data):
        st.write(f"### Q{i+1}: {q['question']}")

        options = ["A", "B", "C", "D"]
        full_options = [
            f"{label}) {text}" for label, text in zip(options, q["choices"])
        ]

        selected = st.radio(
            f"Select an answer for Q{i+1}",
            options=options,
            key=f"q{i+1}",
        )

        st.session_state.user_answers[i] = selected

    # Submit button
    if st.button("Submit Answers"):
        st.session_state.show_results = True

    # Show results
    if st.session_state.show_results:
        st.subheader("📊 Results")

        score = 0
        for i, q in enumerate(st.session_state.quiz_data):
            user = st.session_state.user_answers.get(i)
            correct = q["answer"]

            if user == correct:
                score += 1
                st.success(
                    f"Q{i+1}: Correct! ({correct}) — {q['explanation']}"
                )
            else:
                st.error(
                    f"Q{i+1}: Incorrect. You chose {user}. Correct answer: {correct}. "
                    f"\nExplanation: {q['explanation']}"
                )

        st.write(f"### ⭐ Final Score: {score} / {len(st.session_state.quiz_data)}")
