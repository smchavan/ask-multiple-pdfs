import streamlit as st
import os
from dotenv import load_dotenv
from PyPDF2 import PdfReader
from langchain.text_splitter import CharacterTextSplitter
from langchain.embeddings import OpenAIEmbeddings, HuggingFaceInstructEmbeddings
from langchain.vectorstores import FAISS
from langchain.chat_models import ChatOpenAI
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationalRetrievalChain
from htmlTemplates import css, bot_template, user_template
from langchain.llms import HuggingFaceHub
from langchain.vectorstores import PineconeVectorStore
from langchain_community.llms import OpenAI
import pinecone
#from openai.error import Timeout  # Add this import

# Function to load variables from .env file
def load_env(file_path=".env"):
    with open(file_path) as f:
        for line in f:
            # Ignore comments and empty lines
            if line.strip() and not line.startswith("#"):
                key, value = line.strip().split("=", 1)
                os.environ[key] = value

# Load environment variables from .env
load_env()
openai_api_key = os.environ.get("OPENAI_API_KEY")
pinecone_api_key = os.environ.get("PINECONE_API_KEY")

# Check if the API key is set
if not openai_api_key:
    raise ValueError("OpenAI API key is not set. Please check your .env file.")
if not pinecone_api_key:
    raise ValueError("Pinecone API key is not set. Please check your .env file.")

# Now you can use the retrieved API key in your code
OpenAI.api_key = openai_api_key
OpenAIEmbeddings.api_key = openai_api_key
#pc = Pinecone(api_key=pinecone_api_key)




def get_pdf_text(pdf_docs):
    text = ""
    for pdf in pdf_docs:
        pdf_reader = PdfReader(pdf)
        for page in pdf_reader.pages:
            text += page.extract_text()
    return text


def get_text_chunks(text):
    text_splitter = CharacterTextSplitter(
        separator="\n",
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len
    )
    chunks = text_splitter.split_text(text)
    return chunks


def get_vectorstore(text_chunks):
    load_dotenv()
    # Function to create a vector store using Pinecone
    embeddings = OpenAIEmbeddings()  # Initialize your embeddings object (if needed)
    pinecone.init(api_key=pinecone_api_key) # Initialize Pinecone with your API key
    
    index_name = "langchain-demo"
    index = pinecone.create_index(index_name, dimension=embeddings.embedding_size, metric='cosine')
    # Add text chunks to the index
    for chunk in text_chunks:
        # Generate embedding for the text chunk
        embedding = embeddings.encode(chunk)
        
        # Insert the text chunk and its embedding into the index
        index.upsert(ids=None, vectors=embedding)  # Assuming no specific IDs are provided
    
    return index

def get_conversation_chain(vectorstore):
    llm = ChatOpenAI()
    # llm = HuggingFaceHub(repo_id="google/flan-t5-xxl", model_kwargs={"temperature":0.5, "max_length":512})

    memory = ConversationBufferMemory(
        memory_key='chat_history', return_messages=True)
    conversation_chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=vectorstore.as_retriever(),
        memory=memory
    )
    return conversation_chain


def handle_userinput(user_question):
    response = st.session_state.conversation({'question': user_question})
    st.session_state.chat_history = response['chat_history']

    for i, message in enumerate(st.session_state.chat_history):
        if i % 2 == 0:
            st.write(user_template.replace(
                "{{MSG}}", message.content), unsafe_allow_html=True)
        else:
            st.write(bot_template.replace(
                "{{MSG}}", message.content), unsafe_allow_html=True)


def main():
    load_dotenv()
    st.set_page_config(page_title="Chat with multiple PDFs",
                      page_icon=":books:")
    st.write(css, unsafe_allow_html=True)

    if "conversation" not in st.session_state:
        st.session_state.conversation = None
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = None

    st.header("Chat with multiple PDFs :books:")
    
    with st.sidebar:
        st.subheader("Your documents")
        pdf_docs = st.file_uploader(
            "Upload your PDFs here and click on 'Process'", accept_multiple_files=True)
        if st.button("Process"):
            with st.spinner("Processing"):
                # get pdf text
                raw_text = get_pdf_text(pdf_docs)
                st.write(raw_text)

                # get the text chunks
                text_chunks = get_text_chunks(raw_text)
                st.write(text_chunks)
                # create vector store
                vectorstore = get_vectorstore(text_chunks)

                # create conversation chain
                st.session_state.conversation = get_conversation_chain(
                    vectorstore)
        else:
            st.write("Please upload one or more PDF files.")

    if st.session_state.conversation is not None:
        user_question = st.text_input("Ask a question about your documents:", value="")
        if user_question:
            handle_userinput(user_question)



if __name__ == '__main__':
    main()