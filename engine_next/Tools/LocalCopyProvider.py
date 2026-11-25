"""Local byte-copy factory for standalone clients; no AI generation or service."""

from editor_demo import Demo
from extensions import NodeRegistry


def factory():
    # Reuse the copy implementation without loading optional editor providers.
    registry = NodeRegistry()
    registry.register(
        dict(
            id="copy",
            version="1",
            inputs={"source": {"types": ["image", "mesh"], "required": True}},
            outputs={"result": {"types": ["image", "mesh"], "required": True}},
            context_types=["text", "image"],
            parameters={"properties": {"delay": {"type": "number"}, "fail": {"type": "boolean"}}},
            capabilities=["copy"],
        )
    )
    return registry, {"local-copy": Demo()}
