"""
Sales Management Agent - An intelligent assistant that helps sales teams
analyze sales data and manage inventory across different channels and formats.
Ready for deployment to Foundry Hosted Agent service.
"""

import asyncio
import os
from datetime import datetime

from dotenv import load_dotenv

load_dotenv(override=True)

from agent_framework import (
    ChatAgent,
    HostedCodeInterpreterTool,
    HostedFileSearchTool,
    HostedVectorStoreContent,
    ai_function,
)
from agent_framework.azure import AzureAIClient
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

# ---------------------------------------------------------------------------
# In-memory order log (persists for the lifetime of the server process)
# ---------------------------------------------------------------------------
order_log: list[dict] = []

# Mock supplier catalog
SUPPLIERS = {
    "hand tools": {"name": "ToolCorp Ltd.", "lead_time_days": 5, "unit_cost_multiplier": 0.60},
    "power tools": {"name": "PowerPro Supply", "lead_time_days": 7, "unit_cost_multiplier": 0.55},
    "paint & finishes": {"name": "ColorMax Inc.", "lead_time_days": 3, "unit_cost_multiplier": 0.50},
    "hardware": {"name": "FastenAll Co.", "lead_time_days": 4, "unit_cost_multiplier": 0.65},
    "lumber & building materials": {"name": "TimberLine Wholesale", "lead_time_days": 6, "unit_cost_multiplier": 0.52},
    "electrical": {"name": "VoltEdge Supply", "lead_time_days": 6, "unit_cost_multiplier": 0.58},
    "plumbing": {"name": "AquaFlow Wholesale", "lead_time_days": 5, "unit_cost_multiplier": 0.52},
}


@ai_function
def place_restock_order(product_name: str, quantity: int, category: str = "") -> str:
    """Place a purchase order to restock a product from the supplier.

    Use this function AFTER identifying low-stock items via file_search.
    The order is logged and can be reviewed later with get_restock_orders.

    Args:
        product_name: Name of the product to reorder (e.g. "Pro Cordless Drill 20V").
        quantity: Number of units to order. Must be a positive integer.
        category: Product category (e.g. "POWER TOOLS"). Helps select the right supplier.
    """
    if quantity <= 0:
        return "Error: quantity must be a positive integer."

    # Match category to supplier (case-insensitive)
    lookup = category.lower().strip() if category else product_name.lower()
    supplier = next(
        (s for cat, s in SUPPLIERS.items() if cat in lookup),
        {"name": "Zava General Supply", "lead_time_days": 7, "unit_cost_multiplier": 0.60},
    )

    order_id = f"PO-2026-{abs(hash(product_name + str(len(order_log)))) % 10000:04d}"
    estimated_cost = round(quantity * 12.50 * supplier["unit_cost_multiplier"], 2)

    order = {
        "order_id": order_id,
        "product_name": product_name,
        "category": category or "General",
        "quantity": quantity,
        "supplier": supplier["name"],
        "estimated_cost": estimated_cost,
        "lead_time_days": supplier["lead_time_days"],
        "status": "Confirmed",
        "placed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    order_log.append(order)

    return (
        f"Restock order placed successfully!\n"
        f"Order ID: {order_id}\n"
        f"Product: {product_name}\n"
        f"Quantity: {quantity} units\n"
        f"Supplier: {supplier['name']}\n"
        f"Estimated cost: ${estimated_cost}\n"
        f"Expected delivery: {supplier['lead_time_days']} business days\n"
        f"Status: Confirmed"
    )


@ai_function
def get_restock_orders() -> str:
    """Retrieve all restock orders placed during this session.

    Returns a summary of every purchase order including order ID, product,
    quantity, supplier, cost, and status. Use this when the user asks about
    pending orders or order history.
    """
    if not order_log:
        return "No restock orders have been placed yet this session."

    lines = [f"Restock Orders ({len(order_log)} total):"]
    total_cost = 0.0
    for o in order_log:
        lines.append(
            f"  [{o['order_id']}] {o['product_name']} — "
            f"{o['quantity']} units from {o['supplier']} — "
            f"${o['estimated_cost']} — {o['status']} — "
            f"ETA: {o['lead_time_days']} days — Placed: {o['placed_at']}"
        )
        total_cost += o["estimated_cost"]
    lines.append(f"\nTotal estimated cost: ${total_cost:,.2f}")
    return "\n".join(lines)

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

        # Code interpreter tool for data analysis, calculations, and chart generation
        code_interpreter_tool = HostedCodeInterpreterTool(
            description="Execute Python code for sales data analysis, calculations, and chart generation"
        )
        
        # Create the agent with tools
        agent = ChatAgent(
            chat_client=AzureAIClient(
                project_endpoint=PROJECT_ENDPOINT,
                model_deployment_name=MODEL_DEPLOYMENT_NAME,
                credential=credential,
                agent_name="zava-sales-manager",
            ),
            instructions=AGENT_INSTRUCTIONS,
            tools=[
                file_search_tool,
                code_interpreter_tool,
                place_restock_order,
                get_restock_orders,
            ],
        )

        print("Zava Sales Manager Agent Server running on http://localhost:8088")
        print("Using in-memory thread repository - conversation history persists during this session")
        print(f"File Search enabled with vector store: vs_3tzkgfpKfOgAO5LkHtD4cPJt")
        print("Code Interpreter enabled for data analysis and chart generation")
        print("Custom tools: place_restock_order, get_restock_orders")
        
        server = from_agent_framework(agent, thread_repository=thread_repository)
        await server.run_async()


if __name__ == "__main__":
    asyncio.run(main())

