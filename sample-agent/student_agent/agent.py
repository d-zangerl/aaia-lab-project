"""Bounded action-observation loop."""


import json
from logging import log


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

    history = []
    messages = []
    messages.append(system_message)
    messages.append({
        "role": "user",
        "content": task,
    })

    for turn in range(max_turns):
        responseJson = model(messages)        
        responseObject = json.loads(responseJson)

        if (responseObject.get("final") is not None):
            if emit is not None:
                emit(responseObject)
            return responseObject["final"]

        elif (responseObject.get("tool") is None):
            log("Invalid response, ignoring and retrying: " + responseJson)
            continue  # Invalid response, ignore and retry

        tool_name = responseObject["tool"]
        tool_args = responseObject.get("args", {})

        # TODO validate action

        result = runtime.execute(tool_name, tool_args)
        messages.append({
            "role": "assistant",
            "content": json.dumps(result),
        })