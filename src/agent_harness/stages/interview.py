"""Interview: live Q&A in the terminal, inside the target repo.

This starts the ticket's long-lived Cursor session (--resume carries it
through plan and execute). The agent asks; you answer; up to MAX_ROUNDS
rounds before we force it to plan with what it has.
"""

from __future__ import annotations

from .. import ui
from ..context import LoopContext
from ..models import TicketState
from ..state import TicketWorkspace

MAX_ROUNDS = 3


def _render_answers(answers: dict[str, str]) -> str:
    return "\n".join(f"- {qid}: {answer}" for qid, answer in answers.items())


def run_interview(ctx: LoopContext, ws: TicketWorkspace) -> None:
    ui.stage(f"Interview — {ws.ticket.id}")
    if ws.status == TicketState.TRIAGED:
        ws.transition(TicketState.INTERVIEWING)
        ctx.store.update_status(ws.ticket.id, "interviewing")

    repo = ctx.repo(ws.get_field("repo"))
    triage = ws.read_artifact("triage.json") or "{}"
    task_type = ws.get_field("task_type") or "fix-bug"
    grooming = ws.read_artifact("grooming.json")
    grooming_block = f"\n\nGrooming notes:\n{grooming}" if grooming else ""

    prompt = (
        "/ticket-interview\n\n"
        f"{ws.ticket.summary_block()}\n\n"
        f"Triage result:\n{triage}{grooming_block}\n\n"
        f"Task-type playbook to consult: /{task_type}\n"
        "Explore this repository as needed before asking your questions."
    )
    ws.append_artifact("interview.md", f"# Interview — ticket {ws.ticket.id}\n")

    session_id: str | None = None
    rounds_asked = 0
    for round_number in range(1, MAX_ROUNDS + 1):
        ui.info(f"agent is thinking (round {round_number})...")
        payload, result = ctx.agent.run_json(
            prompt, mode="plan", workspace=repo.path, resume=session_id
        )
        session_id = result.session_id or session_id
        ws.set_field("session_id", session_id)

        if not isinstance(payload, dict) or payload.get("status") == "ready":
            break
        questions = payload.get("questions", [])
        if not questions:
            break
        rounds_asked = round_number

        answers: dict[str, str] = {}
        for q in questions:
            answer = ui.ask_question(
                q.get("question", "?"),
                q.get("why_it_matters", ""),
                q.get("options") or None,
            )
            answers[q.get("id", q.get("question", "?"))] = answer or "(no answer — you decide)"
            ws.append_artifact(
                "interview.md",
                f"\n**Q ({q.get('id', '')}):** {q.get('question', '')}\n\n**A:** {answer}\n",
            )

        last_round = round_number == MAX_ROUNDS
        prompt = f"Developer answers:\n{_render_answers(answers)}\n\n" + (
            "That was the final question round. Reply ready."
            if last_round
            else "Ask a follow-up round only if genuinely needed; otherwise reply ready."
        )

    ws.set_field("interview_rounds", rounds_asked)
    ui.info("interview complete — moving to plan")
