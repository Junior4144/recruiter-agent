from google.adk.agents.llm_agent import Agent

root_agent = Agent(
    model='gemini-3.6-flash',
    name='root_agent',
    description='A helpful assistant for user questions.',
    instruction='You are a recruiter with years of experience reviewing resumes on YouTube. Give direct, practical feedback in a conversational tone based on your expertise.',
)
