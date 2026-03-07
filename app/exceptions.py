class AppException(Exception):
    def __init__(self, message: str = "Error", status_code: int = 400, data=None):
        self.message = message
        self.status_code = status_code
        self.data = data
        super().__init__(message)


class NotFoundError(AppException):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, 404)


class UnauthorizedError(AppException):
    def __init__(self, message: str = "Unauthorized"):
        super().__init__(message, 401)


class ForbiddenError(AppException):
    def __init__(self, message: str = "Forbidden"):
        super().__init__(message, 403)


class ValidationError(AppException):
    def __init__(self, message: str = "Validation failed"):
        super().__init__(message, 422)


class ConflictError(AppException):
    def __init__(self, message: str = "Resource already exists"):
        super().__init__(message, 409)


# RAG-specific errors
class SearchError(AppException):
    pass


class EmbeddingError(SearchError):
    def __init__(self, message: str = "Embedding generation failed"):
        super().__init__(message, 500)


class VectorDBError(SearchError):
    def __init__(self, message: str = "Vector DB error"):
        super().__init__(message, 500)


class KnowledgeBaseNotFoundError(NotFoundError):
    def __init__(self, kb_id: int):
        super().__init__(f"Knowledge base {kb_id} not found")


class DocumentNotFoundError(NotFoundError):
    def __init__(self, doc_id: int):
        super().__init__(f"Document {doc_id} not found")


class DocumentProcessingError(AppException):
    def __init__(self, message: str = "Document processing failed"):
        super().__init__(message, 500)


# LLM-specific errors
class LLMError(AppException):
    pass


class LLMProviderNotFoundError(NotFoundError):
    def __init__(self, provider_id: str):
        super().__init__(f"LLM provider '{provider_id}' not found")


class LLMModelNotFoundError(NotFoundError):
    def __init__(self, model_id: str):
        super().__init__(f"LLM model '{model_id}' not found")


class LLMStreamError(LLMError):
    def __init__(self, message: str = "LLM streaming error"):
        super().__init__(message, 500)


# PPT-specific errors
class ConversationNotFoundError(NotFoundError):
    def __init__(self, conversation_id: str):
        super().__init__(f"Conversation '{conversation_id}' not found")


class StageTransitionError(AppException):
    def __init__(self, current: str, target: str):
        super().__init__(f"Cannot transition from '{current}' to '{target}'", 400)
