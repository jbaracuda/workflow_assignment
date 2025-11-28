import streamlit as st
import requests

# ------------------------------------------------------
# CONFIG
# ------------------------------------------------------
st.set_page_config(
    page_title="Movie Study Guide Workflow",
    layout="centered",
)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# ------------------------------------------------------
# SESSION STATE INIT
# ------------------------------------------------------
for key in [
    "normalized_title",
    "metadata_paragraph",
    "metadata_poster",
    "synopsis",
    "quiz",
    "selected_answer",
]:
    if key not in st.session_state:
        st.session_state[key] = None


# ------------------------------------------------------
# OPENROUTER LLM CALL
# ------------------------------------------------------
def llm(prompt):
    headers = {
        "Authorization": f"Bearer {st.secrets['OPENROUTER_API_KEY']}",
        "Content-Type": "application/json",
    }

    body = {
        "model": "meta-llama/llama-3.1-8b-instruct:free",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 400,
    }

    r = requests.post(OPENROUTER_URL, json=body, headers=headers)
    r.raise_for_status()

    return r.json()["choices"][0]["message"]["content"].strip()


# ------------------------------------------------------
# OMDb FETCH
# ------------------------------------------------------
def fetch_omdb(title):
    url = f"http://www.omdbapi.com/?t={title}&apikey={st.secrets['OMDB_API_KEY']}"
    r = requests.get(url)
    r.raise_for_status()
    data = r.json()

    if data.get("Response") == "False":
        return None
    return data


# ------------------------------------------------------
# QUIZ BUILDER (Agent D)
# ------------------------------------------------------
def build_quiz(summary):
    quiz_prompt = f"""
Create a 4-question multiple choice quiz about the following movie background info:

{summary}

Return the quiz in JSON with the structure:
{{
  "questions": [
    {{
      "question": "...",
      "options": ["A", "B", "C", "D"],
      "answer": "B",
      "explanation": "..."
    }},
    ...
  ]
}}
"""

    import json
    quiz_raw = llm(quiz_prompt)

    try:
        return json.loads(quiz_raw)
    except:
        return None


# ------------------------------------------------------
# UI
# ------------------------------------------------------
st.title("🎬 Movie Study Guide Workflow")
movie_input = st.text_input("What is your favorite movie?")

run_btn = st.button("Generate", type="primary")


# ------------------------------------------------------
# MAIN WORKFLOW
# ------------------------------------------------------
if run_btn and movie_input.strip() != "":
    st.session_state.selected_answer = None  # reset quiz selection each run

    # -------------------------
    # Agent A — Normalize Title
    # -------------------------
    title_prompt = f"Normalize this movie title to its official capitalization: {movie_input}"
    normalized = llm(title_prompt)
    st.session_state.normalized_title = normalized

    # -------------------------
    # Agent B — Metadata
    # -------------------------
    omdb = fetch_omdb(normalized)

    if omdb is None:
        st.session_state.metadata_paragraph = "Movie not found in OMDb. Check your title or API key."
        st.session_state.metadata_poster = None
        st.session_state.synopsis = None
        st.session_state.quiz = None
    else:
        poster = omdb.get("Poster", None)

        info_prompt = f"""
Write a concise movie background paragraph using the following metadata:

{omdb}

Include:
- Context about the film production
- Short background about the director
- Short background about the main actors
"""

        paragraph = llm(info_prompt)
        st.session_state.metadata_paragraph = paragraph
        st.session_state.metadata_poster = poster

        # -------------------------
        # Agent C — Study Guide Summary
        # -------------------------
        synopsis_prompt = f"Write a short study guide style summary of the movie '{normalized}'."
        syn = llm(synopsis_prompt)
        st.session_state.synopsis = syn

        # -------------------------
        # Agent D — Quiz
        # -------------------------
        quiz = build_quiz(paragraph)
        st.session_state.quiz = quiz


# ------------------------------------------------------
# ALWAYS SHOW AGENTS IF THEY HAVE DATA
# ------------------------------------------------------

# Agent A
if st.session_state.normalized_title:
    st.header("Agent A — Normalize Title")
    st.success(f"**{st.session_state.normalized_title}**")

# Agent B
if st.session_state.metadata_paragraph:
    st.header("Agent B — Movie Background")

    if st.session_state.metadata_poster:
        st.image(st.session_state.metadata_poster, width=300)

    st.write(st.session_state.metadata_paragraph)

# Agent C
if st.session_state.synopsis:
    st.header("Agent C — Study Guide Summary")
    st.write(st.session_state.synopsis)

# Agent D — Quiz
if st.session_state.quiz:
    st.header("Agent D — Quiz")

    qset = st.session_state.quiz.get("questions", [])

    for i, q in enumerate(qset):
        st.subheader(f"Question {i+1}")
        st.write(q["question"])

        # persistent radio buttons
        choice = st.radio(
            f"Select an answer for Q{i+1}",
            q["options"],
            key=f"quiz_q{i}",
        )

        if st.button(f"Check Answer for Q{i+1}", key=f"check_{i}"):
            if choice == q["answer"]:
                st.success("Correct!")
            else:
                st.error(f"Incorrect. The correct answer is {q['answer']}.")
            st.info(q["explanation"])
