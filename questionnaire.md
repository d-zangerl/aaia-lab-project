# Week 1 questionnaire

Name and collaborators: Daniel Zangerl

Answer each question in two to five clear sentences, using your own implementation.

1. How does your agent move from a task to a tool call, an observation, and its next action?

The agent creates a system message and the user task, then asks the model for exactly one JSON object. If that JSON contains a tool call, the runtime validates the tool name and arguments before execution. The tool result is appended back into the conversation history as data, and the next model turn decides whether it needs another tool or a final answer.

2. How does the model choose a tool, and how does your program decide whether it may run?

The model chooses a tool by returning a JSON object with a tool name and its argument map. My program checks that the JSON parses, that the tool exists in the registry, and that the required argument names match exactly. After that, the runtime checks the active mode and tool permissions before executing anything.

3. How do read-only and edit mode differ? Why does bash need special treatment?

Read-only mode allows only list, read, search, and approved fetch operations. Edit mode adds file creation and modification, but bash still needs special treatment because it can run arbitrary commands and bypass the normal file boundaries. It therefore needs an explicit human approval prompt and is denied unless the user types exactly yes.

4. What happens when a tool fails, the model returns invalid JSON, or the turn limit is reached?

Tool failures are converted into structured result objects and handed back to the model as observations rather than as instructions. Invalid JSON consumes one turn and is turned into an error observation so the model can recover with a valid response. If the loop reaches its turn limit, the controller stops and returns a clear termination value such as turn_limit instead of silently continuing.

5. Where did the injected instruction enter, what did it request, and how did your agent respond before and after your changes?

The injected instruction enters through untrusted file or fetched content, not from the system prompt. In the attack scenario it tries to persuade the agent to do a forbidden action such as editing protected code or skipping validation. Before the final hardening, a weak agent could obey it; after the changes, the runtime rejects the forbidden action and the result is treated as untrusted data rather than an instruction.

6. Would you accept the service repair? Explain what you checked, one remaining limitation, and how you verified any AI-generated code.

I would accept the service repair only if the business rules and acceptance tests still match, protected files remain untouched, and the added regression test covers the bug. One remaining limitation is that a local model can still make reasoning mistakes or be misled by hostile data even when the runtime is strict. 
Sadly in these tests my agent never managed to create an acceptable outcome. I tried many different ways, but either my code or the model was not strong enough to fix the bug and create a test for it. At best 5/9 tests succeeded in the target-repository.
