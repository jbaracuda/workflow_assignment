import streamlit as st
import requests

st.set_page_config(page_title="Movie Workflow", layout="centered")

# ======================================================
# LLaMA via OpenRouter (FREE)
# ======================================================
def llama_generate(prompt, max_tokens=200):
    url = "https://openrouter.ai/api/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {st.secrets['OPENROUTER_API_KEY']}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "meta-llama/llama-3-8b-instruct",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens
    }

    response = requests.post(url, json=payload, headers=headers)

    if not response.ok:
        st.error(f"OpenRouter Error {response.status_code}: {response.text}")
        st.stop()

    data = response.json()
    return data["choices"][0]["message"]["content"]


# ======================================================
# OMDb API (Free movie Metadata)
# ======================================================
def get_movie_data(title):
    url = f"http://www.omdbapi.com/?t={title}&apikey={st.secrets['OMDB_API_KEY']}&plot=full"
    return requests.get(url).json()


# ======================================================
# Title Normalization (RELIABLE)
# ======================================================
def normalize_title(title: str) -> str:
    return title.title().strip()


# ======================================================
# UI
# ======================================================
st.title("🎬 Movie Workflow — 4 Agent AI System")
st.write("Uses **LLaMA-3** via OpenRouter (free) + OMDb for movie data.")

movie_title = st.text_input("What is your favorite movie? 🎥")

if st.button("Run Workflow") and movie_title.strip():

    # --------------------------------------------------
    # AGENT A — Normalize Movie Title
    # --------------------------------------------------
    st.markdown("## 🧩 Agent A — Normalize Title")

    normalized = normalize_title(movie_title)

    st.success(f"Normalized Title: **{normalized}**")

    # --------------------------------------------------
    # AGENT B — Search OMDb for Metadata + Poster
    # --------------------------------------------------
    st.markdown("## 🎞️ Agent B — Movie Metadata")

    info = get_movie_data(normalized)

    if info.get("Response") == "False":
        st.error("Movie not found in OMDb.")
        st.stop()

    # Poster
    if info.get("Poster") and info["Poster"] != "N/A":
        st.image(info["Poster"], width=300)

    # Metadata
    st.subheader("Movie Details")
    st.json({
        "Title": info.get("Title"),
        "Year": info.get("Year"),
        "Genre": info.get("Genre"),
        "Director": info.get("Director"),
        "Actors": info.get("Actors"),
        "Plot": info.get("Plot")
    })

    # --------------------------------------------------
    # AGENT C — Create Full Movie Synopsis
    # --------------------------------------------------
    st.markdown("## 📖 Agent C — AI Synopsis")

    synopsis = llama_generate(
        f"Write a detailed, spoiler-free synopsis for the movie '{normalized}'.",
        max_tokens=250
    )

    st.write(synopsis)

   # --------------------------------------------------
    # AGENT D — Interactive Quiz
    # --------------------------------------------------
    st.markdown("## 📝 Agent D — Interactive Quiz Generator")
    
    quiz_json = llama_generate(
        f"""
        Create **5 multiple-choice questions** about the movie '{normalized}'.
        Use this synopsis:
        {synopsis}
    
        RETURN THE RESULT IN THIS EXACT JSON FORMAT — NO EXTRA TEXT:
    
        {{
            "questions": [
                {{
                    "question": "text",
                    "choices": ["A text", "B text", "C text", "D text"],
                    "answer": "A",
                    "explanation": "Explain why this is correct"
                }}
            ]
        }}
        """,
        max_tokens=450
    )
    
    import json
    
    try:
        quiz_data = json.loads(quiz_json)
        questions = quiz_data["questions"]
    except:
        st.error("AI returned invalid quiz JSON. Here is the raw output:")
        st.write(quiz_json)
        st.stop()
    
    # Store user answers
    user_answers = {}
    
    st.write("### 🎯 Answer the questions below:")
    
    for i, q in enumerate(questions):
        st.write(f"#### Q{i+1}: {q['question']}")
        user_answers[i] = st.radio(
            f"Your answer for Q{i+1}",
            options=["A", "B", "C", "D"],
            key=f"q{i}"
        )
    
    if st.button("Submit Quiz"):
        st.markdown("## 📊 Results")
        correct = 0
    
        for i, q in enumerate(questions):
            user = user_answers[i]
            correct_answer = q["answer"]
    
            if user == correct_answer:
                st.success(f"Q{i+1}: Correct! 🎉 ({correct_answer})")
                correct += 1
            else:
                st.error(f"Q{i+1}: Incorrect. You chose {user}, correct is {correct_answer}")
    
            st.write(f"💡 **Explanation:** {q['explanation']}")
            st.write("---")
    
        st.markdown(f"### 🏁 Final Score: **{correct} / {len(questions)}**")
