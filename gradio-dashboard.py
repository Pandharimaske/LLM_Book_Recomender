import pandas as pd 
import numpy as np
from dotenv import load_dotenv

from langchain_community.document_loaders import TextLoader
from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_text_splitters import CharacterTextSplitter
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

import gradio as gr

load_dotenv()

books = pd.read_csv("books_with_emotions.csv")
books["large_thumbnail"] = books["thumbnail"] + "&fife=w800"
books["large_thumbnail"] = np.where(
    books["large_thumbnail"].isna(), "cover-not-found.jpg", books["large_thumbnail"]
)

raw_documents = TextLoader("tagged_description.txt").load()
text_splitter = CharacterTextSplitter(separator="\n", chunk_size=0, chunk_overlap=0)
documents = text_splitter.split_documents(raw_documents)

embedding_function = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
db_books = Chroma.from_documents(documents, embedding_function)


def retrieve_semantic_recommendations(query: str, category: str = "All", tone: str = "All", 
                                       initial_top_k: int = 50, final_top_k: int = 16) -> pd.DataFrame:

    recs = db_books.similarity_search_with_score(query, k=initial_top_k)
    books_list = [int(rec[0].page_content.strip('"').split()[0]) for rec in recs]

    book_recs = books[books["isbn13"].isin(books_list)].head(final_top_k)

    if category != "All":
        book_recs = book_recs[book_recs["simple_categories"] == category].head(final_top_k)

    tone_mapping = {
        "Happy": "joy",
        "Surprising": "surprise",
        "Angry": "anger",
        "Suspenseful": "fear",
        "Sad": "sadness"
    }

    if tone in tone_mapping:
        book_recs = book_recs.sort_values(by=tone_mapping[tone], ascending=False)

    return book_recs


def recommend_books(query: str, category: str, tone: str):
    recommendations = retrieve_semantic_recommendations(query=query, category=category, tone=tone)
    results = []

    for _, row in recommendations.iterrows():
        description = row["description"]
        truncated_description = " ".join(description.split()[:30]) + "..."

        authors_split = row["authors"].split(";")
        if len(authors_split) == 2:
            authors_str = f"{authors_split[0]} and {authors_split[1]}"
        elif len(authors_split) > 2:
            authors_str = f"{', '.join(authors_split[:-1])}, and {authors_split[-1]}"
        else:
            authors_str = row["authors"]

        caption = f"{row['title']} by {authors_str}: {truncated_description}"
        results.append((row["large_thumbnail"], caption))  # ✅ Fixed tuple issue

    return results


categories = ["All"] + sorted(books["simple_categories"].unique())
tones = ["All", "Happy", "Surprising", "Angry", "Suspenseful", "Sad"]

with gr.Blocks(theme=gr.themes.Glass()) as dashboard:
    gr.Markdown("# Semantic Book Recommender")

    with gr.Row():
        user_query = gr.Textbox(label="Please enter a description of a book:", 
                                placeholder="e.g., A story about forgiveness")
        category_dropdown = gr.Dropdown(choices=categories, label="Select a category:", value="All")
        tone_dropdown = gr.Dropdown(choices=tones, label="Select an emotional tone:", value="All")
        submit_button = gr.Button("Find Recommendations")

    gr.Markdown("## Recommendations")
    output = gr.Gallery(label="Recommended books", columns=8, rows=2)

    submit_button.click(fn=recommend_books, inputs=[user_query, category_dropdown, tone_dropdown], outputs=output)

if __name__ == "__main__":
    dashboard.launch(share = True)