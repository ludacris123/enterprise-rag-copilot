from mcp.server.fastmcp import FastMCP
from app.ingestion import ingest
from app.retrieval import retriever

mcp = FastMCP("enterprise-rag-copilot")

@mcp.tool()
def search_knowledge(query: str, tenant_id: str, department: str | None = None) -> list[dict]:
    """Search tenant-scoped enterprise knowledge. This tool is read-only."""
    filters = {"department": department} if department else {}
    hits = retriever.search(query, tenant_id, 6, filters)
    return [{"title": h.chunk.title, "text": h.chunk.text, "score": h.score} for h in hits]

@mcp.tool()
def index_text(title: str, text: str, tenant_id: str, department: str = "general") -> dict:
    """Index approved text. Hosts must expose this tool only to authorized administrators."""
    document_id, chunks = ingest(title, text, tenant_id, {"department": department})
    return {"document_id": document_id, "chunks": chunks}

if __name__ == "__main__":
    mcp.run(transport="stdio")
