import streamlit as st
import requests

st.set_page_config(page_title="Movie Workflow", layout="centered")

# ======================================================
# LLaMA via OpenRouter
# ======================================================
def llama_generate(prompt, max_tokens=250):
    url = "https://openrouter.ai/api/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {st.secrets['OPENROUTER_API_KEY']}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "meta-llama/llama-3-8b-instruct",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.7
    }

    response = requests.post(url, json=payload, headers=headers)

    if not response.ok:
        st.error(f"OpenRouter Error {response.status_code}: {response.text}")
        st.stop()

    return response.json()["choices"][0]["message"]["content"]


# ======================================================
# OMDb Metadata
# ======================================================
def get_movie_data(title):
    url = f"http://www.omdbapi.com/?t={title}&apikey={st.secrets['OMDB_API_KEY']}&plot=full"
    return requests.get(url).json()


# ======================================================
# QUIZ UTILITIES (Agent D)
# ======================================================
def parse_quiz(raw_text):
    """
    Converts the LLaMA quiz text into a structured format:
    returns list of {question, options, correct, explanation}
    """
    quiz = []
    blocks = raw_text.strip().split("\n\n")
    current = {}

    for block in blocks:
        lines = block.strip().split("\n")
        q, opts, ans, exp = None, [], None, None

        for line in lines:
            if line.startswith("Q"):
                q = line[line.index(":") + 1:].strip()

            elif line.startswith(("A)", "B)", "C)", "D)")):
                opts.append(line.strip())

            elif line.lower().startswith("answer"):
                ans = line.split(":")[1].strip()

            elif line.lower().startswith("explanation"):
                exp = line.split(":", 1)[1].strip()

        if q and opts and ans:
            quiz.append({
                "question": q,
                "options": opts,
                "correct": ans,
                "explanation": exp or ""
            })

    return quiz


# ======================================================
# UI
# ======================================================
st.title("🎬 Movie Workflow — Four-Agent System")

movie_title = st.text_input("What is your favorite movie?")

if "quiz_data" not in st.session_state:
    st.session_state.quiz_data = None
if "user_answers" not in st.session_state:
    st.session_state.user_answers = {}
if "show_results" not in st.session_state:
    st.session_state.show_results = False


if st.button("Run Workflow") and movie_title.strip():

    # --------------------------------------------------
    # AGENT A — Normalize Title
    # --------------------------------------------------
    st.header("Agent A — Title Normalization")

    normalized = llama_generate(
        f"Return only the correctly formatted official movie title: {movie_title}",
        max_tokens=25
    ).strip()

    st.success(f"Title: **{normalized}**")

    # --------------------------------------------------
# AGENT B — Paragraph Summary of Metadata (High-Level, No Spoilers)
# --------------------------------------------------
st.header("Agent B — Movie Background")

raw_info = get_movie_data(normalized)

if raw_info.get("Response") == "False":
    st.error("Movie not found in OMDb.")
    st.stop()

# Show poster
if raw_info.get("Poster") and raw_info["Poster"] != "N/A":
    st.image(raw_info["Poster"], width=300)

# High-level, non-spoiler background paragraph
metadata_prompt = f"""
Write a single-paragraph, high-level background overview of the movie '{normalized}'.

REQUIREMENTS:
- DO NOT reveal major plot points, twists, or endings.
- DO NOT describe specific character arcs or detailed motivations.
- Focus only on broad themes, tone, and general premise.
- Include director, genre, year, and why the film is notable.
- Do not mention AI or generation.

Here is the metadata for reference:
Title: {raw_info.get("Title")}
Year: {raw_info.get("Year")}
Genre: {raw_info.get("Genre")}
Director: {raw_info.get("Director")}
Actors: {raw_info.get("Actors")}
Plot: {raw_info.get("Plot")}
"""

metadata_paragraph = llama_generate(metadata_prompt, max_tokens=200)
st.write(metadata_paragraph)



# --------------------------------------------------
# AGENT C — Two-Paragraph Character-Focused Synopsis
# --------------------------------------------------
st.header("Agent C — Synopsis")

synopsis_prompt = f"""
Write a two-paragraph character-focused synopsis of the movie '{normalized}'.

REQUIREMENTS:
- DO NOT repeat the high-level plot summary style used in Agent B.
- Paragraph 1 should describe the central characters, their personalities,
  their roles, and what motivates them—without giving away major plot twists.
- Paragraph 2 should explain how these characters interact, conflict, or develop
  within the story’s setting, again without spoilers.
- Avoid summarizing the entire plot; focus on character dynamics and structure.
- Do not mention AI or generation.
"""

synopsis = llama_generate(synopsis_prompt, max_tokens=350)
st.write(synopsis)


    # --------------------------------------------------
    # AGENT D — Quiz
    # --------------------------------------------------
    st.header("Agent D — Quiz")

    quiz_prompt = f"""
    Using the synopsis below, create a 5-question multiple-choice quiz.
    Each question MUST follow this format:

    Q1: <question>
    A) <option>
    B) <option>
    C) <option>
    D) <option>
    Answer: <letter>
    Explanation: <why this answer is correct>

    REQUIREMENTS:
    - Base every question strictly on the synopsis.
    - Do not mention AI or generation.
    - Provide useful explanations.

    SYNOPSIS:
    {synopsis}
    """

    raw_quiz = llama_generate(quiz_prompt, max_tokens=350)
    quiz = parse_quiz(raw_quiz)

    st.session_state.quiz_data = quiz
    st.session_state.user_answers = {}
    st.session_state.show_results = False


# ======================================================
# SHOW QUIZ (IF AVAILABLE)
# ======================================================
if st.session_state.quiz_data and not st.session_state.show_results:
    st.subheader("Your Quiz")

    for i, q in enumerate(st.session_state.quiz_data):
        st.write(f"**Q{i+1}: {q['question']}**")

        # Radio buttons with persistent state
        st.session_state.user_answers[i] = st.radio(
            f"Choose an answer for question {i+1}:",
            q["options"],
            key=f"q{i}"
        )

        st.write("---")

    if st.button("Submit Answers"):
        st.session_state.show_results = True


# ======================================================
# SHOW RESULTS
# ======================================================
if st.session_state.show_results:
    st.header("Results")

    score = 0
    quiz = st.session_state.quiz_data

    for i, q in enumerate(quiz):
        user_choice = st.session_state.user_answers.get(i, "")
        correct_letter = q["correct"]
        correct_option = [o for o in q["options"] if o.startswith(correct_letter)][0]

        if user_choice.startswith(correct_letter):
            score += 1
            st.success(f"Q{i+1}: Correct! 🎉")
        else:
            st.error(f"Q{i+1}: Incorrect.")

        st.write(f"**Correct Answer:** {correct_option}")
        st.write(f"**Explanation:** {q['explanation']}")
        st.write("---")

    st.subheader(f"Final Score: **{score} / {len(quiz)}**")
