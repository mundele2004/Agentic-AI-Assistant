from langchain_core.tools import tool


def create_rag_tool(retriever):

    @tool
    def rag_search(query: str) -> str:
        """
        Search the uploaded PDF for relevant information.
        """

        docs = retriever.invoke(query)

        context = "\n\n".join(
            doc.page_content
            for doc in docs
        )

        return context

    return rag_search