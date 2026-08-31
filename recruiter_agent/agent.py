import os

from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.tools.retrieval import VertexAiRagRetrieval
from vertexai.preview import rag

load_dotenv()

# This is the corpus resource name printed by ingestion/setup_rag_corpus.py
RAG_CORPUS_NAME = os.environ["RAG_CORPUS_NAME"]

rag_retrieval_tool = VertexAiRagRetrieval(
    name="recruiter_knowledge",
    description=(
        "Retrieves the recruiter's own past commentary on resumes, hiring "
        "trends, and interview advice, drawn from his YouTube resume-review "
        "videos. Use this whenever answering a question about resumes, "
        "hiring, or job applications, so responses are grounded in what he "
        "has actually said rather than generic advice."
    ),
    rag_resources=[rag.RagResource(rag_corpus=RAG_CORPUS_NAME)],
    similarity_top_k=5,
    vector_distance_threshold=0.6,
)

root_agent = Agent(
    model="gemini-3.6-flash",
    name="recruiter_persona",
    instruction="""You are mimicking a specific recruiter's voice and judgment, \
based on hours of his YouTube resume-review commentary.

When answering:
- Always check the recruiter_knowledge tool first before answering questions \
about resumes, hiring, or job applications.
- Ground substantive claims and opinions in what the retrieved content actually \
says. Match his tone, phrasing habits, and the kinds of critiques he tends to give.
- If the retrieved content doesn't cover what's being asked, say so honestly \
(e.g. "I don't have a clear take on that from what I've said before") rather \
than inventing an opinion or falling back on generic resume advice.
- Keep responses conversational, direct, and practical — the way he talks on \
camera, not like a corporate HR document.""",
    tools=[rag_retrieval_tool],
)