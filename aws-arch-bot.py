#!/usr/bin/python3

#########################################################################
# AWS Architecture Bot:
# - takes a query
# - scans given content, from AWS Architecture sections
# - provides an answer based on the query and content
#
# Pre-requisites:
# - pre-processed input file (AWS architecture sections) with embeddings
#########################################################################

import openai
from openai.embeddings_utils import get_embedding, cosine_similarity
import pandas as pd
import tiktoken
import localsecrets #openaikey="sk-xxxx"
from scipy import spatial #calculate vector similarities for search
import ast  # for converting embeddings saved as strings back to arrays

#input
datafile_path = "data.csv"

##openai.api_key = "sk-xxxx"
openai.api_key = localsecrets.openaikey

# embedding model parameters
embedding_model = "text-embedding-ada-002"
embedding_encoding = "cl100k_base"  # this the encoding for text-embedding-ada-002
gpt_model = "gpt-3.5-turbo"

#top-100 results ranked-by-relatedness
def strings_ranked_by_relatedness(
    query: str,
    df: pd.DataFrame,
    relatedness_fn=lambda x, y: 1 - spatial.distance.cosine(x, y),
    top_n: int = 100
) -> tuple[list[str], list[float]]:
    """Returns a list of strings and relatednesses, sorted from most related to least."""
    query_embedding = get_embedding(query, engine = embedding_model)
    ##print(query_embedding) #debug

    strings_and_relatednesses = [
        (row["sections"], relatedness_fn(query_embedding, row["embedding"]), row["url"])
        for i, row in df.iterrows()
    ]
    strings_and_relatednesses.sort(key=lambda x: x[1], reverse=True)
    strings, relatednesses, reference_urls = zip(*strings_and_relatednesses)
    return strings[:top_n], relatednesses[:top_n], reference_urls[:top_n]

def num_tokens(text: str, model: str = gpt_model) -> int:
    """Return the number of tokens in a string."""
    encoding = tiktoken.encoding_for_model(model)
    return len(encoding.encode(text))

#prepare context for chatgpt
def query_message(
    query: str,
    df: pd.DataFrame,
    model: str,
    token_budget: int
) -> str:
    """Return a message for GPT, with relevant source texts pulled from a dataframe."""
    strings, relatednesses, reference_urls = strings_ranked_by_relatedness(query, df)
    introduction = 'Use the below content on the AWS Architecture to answer the subsequent question. If the answer cannot be found in the articles, write "I could not find an answer."'
    question = f"\n\nQuestion: {query}"
    message = introduction
    for string in strings:
        next_article = f'\n\nAWS Architecture section:\n"""\n{string}\n"""'
        if (
            num_tokens(message + next_article + question, model=model)
            > token_budget
        ):
            break
        else:
            message += next_article
    return message + question, reference_urls

def ask_chatgpt(
    query: str,
    #df: pd.DataFrame = df,
    df: pd.DataFrame,
    model: str = gpt_model,
    token_budget: int = 4096 - 500,
    print_message: bool = False,
) -> str:
    """Answers a query using GPT and a dataframe of relevant texts and embeddings."""
    message, reference_urls = query_message(query, df, model=model, token_budget=token_budget)
    if print_message:
        print(message)

    messages = [
        {
            "role": "system",
            "content": "You are an AWS Certified Solutions Architect. Your role is to help customers understand best practices on building on AWS. Return your response in markdown, so you can bold and highlight important steps for customers.",
        },
        {
            "role": "user", "content": message
        }
    ]

    response = openai.ChatCompletion.create(
        model=model,
        messages=messages,
        temperature=0
    )
    response_message = response["choices"][0]["message"]["content"]
    return response_message, reference_urls

if __name__ == '__main__':
  #query = "tell me about s3 best practices"
  query = "best practices for reliability"
  ##query = "tell me about Azure best practices" #debug: "I could not find an answer"
  print(query)

  ##df = pd.read_csv(datafile_path, index_col=0)
  df = pd.read_csv(datafile_path)
  df['embedding'] = df['embedding'].apply(ast.literal_eval) ## convert embeddings from CSV str type back to list type

  answer, reference_urls = ask_chatgpt(query, df)
  print(answer)
  print(reference_urls)
