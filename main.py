"""
Sales Management Agent - An intelligent assistant that helps sales teams
analyze sales data and manage inventory across different channels and formats.
Ready for deployment to Foundry Hosted Agent service.
"""

import asyncio
import os

from dotenv import load_dotenv

load_dotenv(override=True)

from agent_framework import ChatAgent, HostedFileSearchTool, HostedVectorStoreContent
from agent_framework.azure import AzureAIAgentClient
from azure.ai.agentserver.agentframework import from_agent_framework
from azure.ai.agentserver.agentframework.persistence import InMemoryAgentThreadRepository
from azure.identity.aio import DefaultAzureCredential

# Configure these for your Foundry project
# Read the explicit variables present in the .env file
PROJECT_ENDPOINT = os.getenv(
    "PROJECT_ENDPOINT"
)  # e.g., "https://<project>.services.ai.azure.com"
MODEL_DEPLOYMENT_NAME = os.getenv(
    "MODEL_DEPLOYMENT_NAME", "gpt-4.1"
)  # Your model deployment name e.g., "gpt-4.1"

# Load agent instructions from external file
INSTRUCTIONS_FILE = os.path.join(os.path.dirname(__file__), "agent_instructions.md")
with open(INSTRUCTIONS_FILE, "r", encoding="utf-8") as f:
    AGENT_INSTRUCTIONS = f.read()

async def main():
    """Main function to run the agent as a web server."""
    # Create thread repository for maintaining conversation context across requests
    thread_repository = InMemoryAgentThreadRepository()
    
    async with DefaultAzureCredential() as credential:
        # File search tool with existing vector store containing product catalog and sales data
        vector_store_content = HostedVectorStoreContent(vector_store_id="vs_3tzkgfpKfOgAO5LkHtD4cPJt")
        file_search_tool = HostedFileSearchTool(
            inputs=[vector_store_content],
            max_results=20,
            description="Search Zava product catalog and sales data from the vector store"
        )
        
        # Create the agent with tools
        agent = ChatAgent(
            chat_client=AzureAIAgentClient(
                project_endpoint=PROJECT_ENDPOINT,
                model_deployment_name=MODEL_DEPLOYMENT_NAME,
                credential=credential,
            ),
            instructions=AGENT_INSTRUCTIONS,
            tools=[file_search_tool],
        )

        print("Zava Sales Manager Agent Server running on http://localhost:8088")
        print("Using in-memory thread repository - conversation history persists during this session")
        print(f"File Search enabled with vector store: vs_3tzkgfpKfOgAO5LkHtD4cPJt")
        
        server = from_agent_framework(agent, thread_repository=thread_repository)
        await server.run_async()


if __name__ == "__main__":
    asyncio.run(main())

