"""Bounded action-observation loop."""


import json
from logging import log


def get_result(termination, result):
    return {
        "termination": termination,
        "result": result,
    }


def run_agent(model, runtime, task, max_turns=15, emit=None):
    """Run the model and tools until a defined termination condition.

    `model(messages)` returns one JSON string. `runtime.execute(action)` returns
    one result dictionary. The handout defines the protocol, emitted events, and
    required termination values.
    """

    system_message = {
        "role": "system",
        "content": "Return exactly one JSON object per response. Accept only one of these forms: {\"tool\":\"<name>\",\"args\":{...}} or {\"final\":\"text\"}. Do not add any extra text, markdown, or explanation",
    }

    messages = [
        system_message,
        {"role": "user", "content": task},
    ]

    for _ in range(max_turns):
        try:
            response_json = model(messages)
        except TimeoutError:
            return get_result("model_error", "model timeout")
        except KeyboardInterrupt:
            return get_result("cancelled", "cancelled by user")

        try:
            response_object = json.loads(response_json)
        except json.JSONDecodeError:
            error_observation = {
                "role": "assistant",
                "content": json.dumps({"error": f"invalid JSON: {response_json}"}),
            }
            messages.append(error_observation)
            if emit is not None:
                emit({"result": {"error": "invalid JSON"}})
            continue

        if response_object.get("final") is not None:
            result = get_result("final", response_object["final"])
            if emit is not None:
                emit(result)
            return result

        if response_object.get("tool") is None:
            log(40, "Invalid response, ignoring and retrying: " + response_json)
            messages.append({
                "role": "assistant",
                "content": json.dumps({"error": f"invalid response: {response_json}"}),
            })
            if emit is not None:
                emit({"result": {"error": "invalid response"}})
            continue

        action = response_object
        try:
            tool_result = runtime.execute(action)
        except Exception as exc:  # pragma: no cover - defensive fallback for runtime failures
            tool_result = {"status": "error", "output": str(exc)}

        messages.append({
            "role": "assistant",
            "content": json.dumps({"result": tool_result}),
        })

        if emit is not None:
            emit({"result": tool_result})

    return get_result("turn_limit", "maximum turns exceeded")