from pyzotero import zotero
from dotenv import load_dotenv
import os
import shutil
import pinecone
import time
import subprocess
import asyncio
import cachetools
from cachetools import cached

load_dotenv()

# Set up a cache with a maximum size of 1000 items
cache = cachetools.LRUCache(maxsize=1000)

# In case you want to clear the cache
# cache.clear()

# Custom key function that converts lists and dictionaries into hashable structures
def custom_key(*args, **kwargs):
    def convert(obj):
        if isinstance(obj, list):
            return tuple(convert(e) for e in obj)
        elif isinstance(obj, dict):
            return frozenset((k, convert(v)) for k, v in obj.items())
        else:
            return obj

    return tuple(convert(arg) for arg in args)

@cached(cache, key=custom_key)
def get_everything(zot, query):
    return zot.everything(query)

def search_zotero(user_id, library_type, api_key, document_title):
    # Create a Zotero instance
    zot = zotero.Zotero(user_id, library_type, api_key)

    # Provide the title you want to search for
    search_title = document_title

    journal_articles = get_everything(zot, zot.items(itemType='journalArticle'))
    conference_papers = get_everything(zot, zot.items(itemType='conferencePaper'))

    all_papers = journal_articles + conference_papers
    # Find the parent item(s) with the provided title
    parent_items = [item for item in all_papers if item['data']['title'].lower().find(search_title.lower()) != -1]

    # Display the parent_items for debugging
    print("Parent Items:")
    for parent_item in parent_items:
        print(f"Title: {parent_item['data']['title']}, Key: {parent_item['data']['key']}")
    print()

    # Specify the target folder and the new file name
    target_folder = '/Users/ekaterinakrivich/Sandbox/gpt4-pdf-chatbot-langchain/docs'
    new_file_name = 'taxonomy.pdf'


    for parent_item in parent_items:
        # Find the child attachments of the parent item
        child_attachments = zot.children(parent_item['data']['key'])
        
        for attachment in child_attachments:
            if attachment['data']['contentType'] == 'application/pdf':
                # Get the absolute storage path
                zotero_storage = os.path.expanduser('~/Zotero/storage')  # Modify this path if your storage location is different
                pdf_path = os.path.join(zotero_storage, attachment['data']['key'], attachment['data']['filename'])
                
                print(f"Title: {attachment['data']['title']}")
                print(f"PDF Path: {pdf_path}\n")

                # Copy the file to the target folder with the new file name
                target_file_path = os.path.join(target_folder, new_file_name)
                shutil.copy(pdf_path, target_file_path)
    return 1

def pinecone_index():
    pinecone.init(api_key=os.environ['PINECONE_API_KEY'], environment='us-west4-gcp')
    index_name = "pdf"
    try:
        print(f"Deleting index '{index_name}'...")
        pinecone.delete_index(index_name)
    except pinecone.exceptions.NotFoundException:
        print(f"Index '{index_name}' does not exist.")
    # Wait for a few seconds to ensure the index deletion is propagated
    time.sleep(5)
    # Check if the index was deleted
    existing_indexes = pinecone.list_indexes()
    if index_name not in existing_indexes:
        print(f"Index '{index_name}' was deleted successfully.")
        pinecone.create_index(index_name, metric="cosine", shards=1, dimension=1536)
        print(f"Index '{index_name}' was created successfully.")
    else:
        print(f"Index '{index_name}' still exists.")
    return 1

async def main():
    api_key = os.environ['ZOTERO_API_KEY']
    user_id = os.environ['ZOTERO_USER_ID']
    document_title = os.environ['DOCUMENT_TITLE']
    library_type = 'user'  # or 'group'
    await asyncio.gather(
        asyncio.to_thread(search_zotero, user_id, library_type, api_key, document_title),
        asyncio.to_thread(pinecone_index)
    )
    time.sleep(15)
    pnpm_command = "pnpm run ingest"
    try:
        subprocess.run(pnpm_command, shell=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"An error occurred while running the pnpm command: {e}")
    else:
        print("The pnpm command executed successfully.")

asyncio.run(main())