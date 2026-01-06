from typing import Optional, Dict, Any, List


class GradioNode:
    def __init__(
        self,
        src: str,
        name: Optional[str] = None,
        is_interaction_point: bool = False,
    ):
        self.src = src
        self.name = name or src.split("/")[-1]
        self.is_interaction_point = is_interaction_point
        self.inputs: List[Dict[str, Any]] = []
        self.outputs: List[Dict[str, Any]] = []
        self._api_info: Optional[Dict[str, Any]] = None

    def __repr__(self):
        return f"GradioNode(name={self.name}, src={self.src})"

