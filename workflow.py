from langgraph.graph import StateGraph, END

from models import AgentState
from nodes import (
    ai_planner_node,
    validator_node,
    py_trimmer_node,
    final_corrector_node,
    processor_node,
    route_planner,
)


def build_workflow():
    workflow = StateGraph(AgentState)

    workflow.add_node("ai_planner", ai_planner_node)
    workflow.add_node("validator", validator_node)
    workflow.add_node("py_trimmer", py_trimmer_node)
    workflow.add_node("final_corrector", final_corrector_node)
    workflow.add_node("processor", processor_node)

    workflow.set_entry_point("ai_planner")

    workflow.add_conditional_edges(
        "validator",
        route_planner,
        {
            "ai_planner": "ai_planner",
            "final_corrector": "final_corrector",
            "py_trimmer": "py_trimmer",
        },
    )

    workflow.add_edge("ai_planner", "validator")
    workflow.add_edge("py_trimmer", "final_corrector")
    workflow.add_edge("final_corrector", "processor")
    workflow.add_edge("processor", END)

    return workflow.compile()
