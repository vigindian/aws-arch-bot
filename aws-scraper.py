#!/usr/bin/python3

from bs4 import BeautifulSoup
import requests
import pandas as pd
from tqdm import tqdm
from urllib.parse import urlparse
import json
import re #regex
import tiktoken
import openai
import localsecrets
#from openai.embeddings_utils import get_embedding

openai.api_key = localsecrets.openaikey

embedding_model = "text-embedding-ada-002"
embedding_encoding = "cl100k_base"  # this the encoding for text-embedding-ada-002
min_tokens = 13
##max_tokens = 8000  # the maximum for text-embedding-ada-002 is 8191
max_tokens = 4096 - 500 # the maximum for gpt-3.5-turbo is 4096

#debugMode = True
debugMode = False 

#URL_AWS_WELL_ARCH = "https://aws.amazon.com/architecture/well-architected/?wa-lens-whitepapers.sort-by=item.additionalFields.sortDate&wa-lens-whitepapers.sort-order=desc&wa-guidance-whitepapers.sort-by=item.additionalFields.sortDate&wa-guidance-whitepapers.sort-order=desc"
URL_AWS_WELL_ARCH = "https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html"

# create empty dict
dict_href_links = {}

def get_urltext(url):
  r = requests.get(url)
  return r.text

#get all sub-links from given URL
def get_links(url):
  #identify base_url from given URL
  parse_url = urlparse(url)
  base_url = parse_url.scheme + "://" + parse_url.netloc + "/"
  #print(base_url)
  html_text = get_urltext(url)
  soup = BeautifulSoup(html_text, "html.parser")
  list_links = []
  ldict_links = {}
  for link in soup.find_all("a", href=True):
    if debugMode:
      print(link["href"])

    # Append to list if new link contains original link
    if str(link["href"]).startswith((str(base_url))):
      list_links.append(link["href"])

    if debugMode:
        print(list_links)

    # Include all href that do not start with url link but with "/"
    if str(link["href"]).startswith("/"):
      if link["href"] not in dict_href_links:
        print(link["href"])
        dict_href_links[link["href"]] = None
        link_with_www = base_url + link["href"][1:]
        print("adjusted link =", link_with_www)
        list_links.append(link_with_www)

        # Convert list of links to dictionary and define keys as the links and the values as "Not-checked"
        ldict_links = dict.fromkeys(list_links, "Not-checked")
        #return dict_links
  return ldict_links

def get_subpage_links(l):
  for link in tqdm(l):
    print(link)
    # If not crawled through this page start crawling and get links
    if l[link] == "Not-checked":
      dict_links_subpages = get_links(link)
      print(dict_links_subpages)
      # Change the dictionary value of the link to "Checked"
      l[link] = "Checked"
      print("checked")
    else:
      # Create an empty dictionary in case every link is checked
      dict_links_subpages = {}

    # Add new dictionary to old dictionary
    l = {**dict_links_subpages, **l}
  return l

def get_next_page(url):
  html_text = get_urltext(url)
  soup = BeautifulSoup(html_text, "html.parser")
  try:
    #<div accesskey="n" class="next-link" href="./definitions.html" id="next">Definitions</div>
    next_link = soup.find("div", {"id": "next"})
    next_link_path = next_link["href"].split("/")[1] #ignore dot "."
    url_main = url.rsplit("/", 1)[0] #remove page-name from path
    ##next_link_fullurl = (url_main + "/" + next_link_path).replace(".","")
    next_link_fullurl = url_main + "/" + next_link_path
  except:
    next_link_fullurl = None

  return next_link_fullurl


def num_tokens_from_string(string: str, encoding_name: str) -> int:
    """Returns the number of tokens in a text string."""
    encoding = tiktoken.get_encoding(encoding_name)
    num_tokens = len(encoding.encode(string))
    return num_tokens

#remove special characters
def clean_data(source_data: str):
  cleandata1 = (re.sub(r'[^a-zA-Z0-9\s]+', '', source_data)).replace("\n","").strip().lower()
  cleandata = ' '.join(cleandata1.split()) #remove additional white-space
  return cleandata

def get_embedding(text, model):
   text = str(text).replace("\n", " ")
   return openai.Embedding.create(input = [text], model=model)['data'][0]['embedding']

def get_page_details(url):
  #r = requests.get(URL_AWS_WELL_ARCH).text
  html_text = get_urltext(url)
  soup = BeautifulSoup(html_text, "html.parser")

  if debugMode:
      print(soup)

  #scrape the table using bs
  title = soup.find("title").string
  if debugMode:
      print(title) #debug

  main_article = soup.find(id="main-col-body")  # main text of article
  # Get text sections
  text_sections = main_article.findAll("p")
  text_list = []

  for list_item in text_sections:
    clean_text = clean_data(list_item.text)
    text_list.append(clean_text)

  # Get info in tables
  tables = main_article.findAll("table")

  for table in tables:
    # Add all ths and tds
    tds = table.findAll("td")
    ths = table.findAll("th")

    for th in ths:
      th_clean_text = clean_data(th.text)
      text_list.append(th_clean_text)

    for td in tds:
      td_clean_text = clean_data(td.text)
      text_list.append(td_clean_text)

  json_obj = {}
  num_tokens = num_tokens_from_string(str(text_list), embedding_encoding)
  #ignore sections with less tokens, to retain only meaningful info; and enforce max-token-limit
  if num_tokens > min_tokens and num_tokens < max_tokens:
    json_obj["url"] = url
    json_obj["title"] = title
    json_obj["sections"] = text_list
    json_obj["no_tokens"] = num_tokens
    #json_obj["embedding"] = get_embedding(text_list, engine=embedding_model) #uses openai-built-in
    json_obj["embedding"] = get_embedding(text_list, model=embedding_model) #custom function

  #print(json_obj)
  return json_obj

#run only when executed in the main file and not when it is imported in some other file
if __name__ == '__main__':

  #alllinks=get_links(URL_AWS_WELL_ARCH)
  #print(alllinks)

  #first-page
  jsonobj=get_page_details(URL_AWS_WELL_ARCH)
  if debugMode:
    print(jsonobj)
  if jsonobj:
    df = pd.json_normalize(jsonobj)
    df.to_csv("data.csv", index=False, encoding="utf-8")

  #subsequent-pages
  urlnext = URL_AWS_WELL_ARCH
  counter = None
  while counter != 0:
    nextlink = get_next_page(urlnext)
    if debugMode:
        print(nextlink)

    if nextlink == None:
        counter = 0
    else:
        jsonobj=get_page_details(nextlink)
        if jsonobj:
          df = pd.json_normalize(jsonobj)
          df.to_csv("data.csv", mode="a", index=False, header=False, encoding="utf-8") #append-without-header

    urlnext = nextlink
