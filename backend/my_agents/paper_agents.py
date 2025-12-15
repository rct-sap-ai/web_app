from agents import Agent, handoff

intro_agent = Agent(
    name="Intro Agent",
    instructions="""
You write the Introduction section of a scientific paper.
Ask concise questions until you can draft the section.
Wrap drafts in:
BEGIN_DRAFT
...
END_DRAFT
Ask the user to reply CONFIRM to proceed.
On CONFIRM, call transfer_to_methods_agent.
""",
)

methods_agent = Agent(
    name="Methods Agent",
    instructions="""
You write the Methods section.
Ask for reproducibility details.
Draft, then request CONFIRM.
On CONFIRM, call transfer_to_results_agent.
""",
)

results_agent = Agent(
    name="Results Agent",
    instructions="""
You write the Results section.
Elicit quantitative findings.
Draft, then request CONFIRM.
On CONFIRM, call transfer_to_discussion_agent.
""",
)

discussion_agent = Agent(
    name="Discussion Agent",
    instructions="""
You write the Discussion section.
Interpret results, limitations, and future work.
Draft, then request CONFIRM.
When confirmed, say the paper is complete.
""",
)

# Wire handoffs
intro_agent.handoffs = [handoff(methods_agent)]
methods_agent.handoffs = [handoff(results_agent)]
results_agent.handoffs = [handoff(discussion_agent)]

# Export entry point
START_AGENT = intro_agent
