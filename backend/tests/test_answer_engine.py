from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from backend.answer_engine import AnswerEngine
from backend.knowledge_backend import EvidenceCandidate, RetrievalResult


class FakeKnowledgeBackend:
    name = "fake_pgvector"
    version = "fake-v1"

    def __init__(self, candidates: list[EvidenceCandidate]) -> None:
        self.candidates = candidates

    async def retrieve(self, db, owner_id: str, question: str, *, limit: int = 3) -> RetrievalResult:
        return RetrievalResult(
            owner_name="Test Owner",
            snapshot_version=7,
            candidates=self.candidates[:limit],
        )


async def fake_streamer(system_prompt: str, user_message: str) -> AsyncIterator[str]:
    assert "owner-approved evidence" in system_prompt
    assert "exp_1" in system_prompt
    assert user_message == "What backend experience does Test Owner have?"
    yield "Test Owner has backend platform experience using FastAPI and PostgreSQL."


@pytest.mark.asyncio
async def test_answer_engine_uses_llm_streamer_for_supported_evidence():
    engine = AnswerEngine(
        knowledge_backend=FakeKnowledgeBackend(
            [
                EvidenceCandidate(
                    chunk_id="chunk_1",
                    source_type="experience",
                    source_id="exp_1",
                    title="Platform Lead at Beta Labs",
                    quote="Leads backend platform development using FastAPI and PostgreSQL.",
                    text="experience Platform Lead backend FastAPI PostgreSQL",
                    metadata={},
                    relevance=0.9,
                )
            ]
        ),
        token_streamer=fake_streamer,
    )

    response = await engine.answer(
        await engine.plan(None, "test_owner", "What backend experience does Test Owner have?")
    )

    assert response.status == "SUPPORTED"
    assert response.answer == "Test Owner has backend platform experience using FastAPI and PostgreSQL."
    assert response.snapshot_version == 7
    assert response.evidence[0].source_id == "exp_1"


@pytest.mark.asyncio
async def test_answer_engine_refuses_without_sufficient_evidence():
    async def failing_streamer(system_prompt: str, user_message: str) -> AsyncIterator[str]:
        raise AssertionError("LLM should not be called for unanswerable questions")
        yield ""

    engine = AnswerEngine(
        knowledge_backend=FakeKnowledgeBackend([]),
        token_streamer=failing_streamer,
    )

    response = await engine.answer(await engine.plan(None, "test_owner", "Can you make pancakes?"))

    assert response.status == "UNANSWERABLE"
    assert response.evidence == []
    assert "don't have enough information" in response.answer.lower()


@pytest.mark.asyncio
async def test_answer_engine_does_not_answer_unsupported_explanation_subquestion():
    async def poisoned_streamer(system_prompt: str, user_message: str) -> AsyncIterator[str]:
        yield "Test Owner used Java. Inversion of Control in Spring Boot means generic framework knowledge."

    engine = AnswerEngine(
        knowledge_backend=FakeKnowledgeBackend(
            [
                EvidenceCandidate(
                    chunk_id="chunk_java",
                    source_type="project",
                    source_id="proj_java",
                    title="RAFT Consensus Visualization Tool",
                    quote="Built a realtime distributed cluster visualization tool using Java Spring Boot.",
                    text="project RAFT Consensus Visualization Tool Java Spring Boot",
                    metadata={},
                    relevance=0.9,
                )
            ]
        ),
        token_streamer=poisoned_streamer,
    )

    response = await engine.answer(
        await engine.plan(
            None,
            "test_owner",
            "What project did he use Java for and explain IoC of Spring Boot?",
        )
    )

    assert response.status == "PARTIAL"
    assert "RAFT Consensus Visualization Tool" in response.answer
    assert "Inversion of Control" not in response.answer
    assert "generic framework knowledge" not in response.answer
    assert "does not contain enough detail" in response.answer


@pytest.mark.asyncio
async def test_answer_engine_uses_llm_for_partial_non_explanatory_answers():
    async def partial_streamer(system_prompt: str, user_message: str) -> AsyncIterator[str]:
        assert "partially supports" in system_prompt
        yield "Test Owner has some backend evidence, but the profile is missing details."

    engine = AnswerEngine(
        knowledge_backend=FakeKnowledgeBackend(
            [
                EvidenceCandidate(
                    chunk_id="chunk_partial",
                    source_type="skill",
                    source_id="skill_backend",
                    title="Backend systems",
                    quote="Builds durable APIs.",
                    text="skill Backend systems APIs",
                    metadata={},
                    relevance=0.12,
                )
            ]
        ),
        token_streamer=partial_streamer,
    )

    response = await engine.answer(await engine.plan(None, "test_owner", "Tell me about backend APIs"))

    assert response.status == "PARTIAL"
    assert response.answer == "Test Owner has some backend evidence, but the profile is missing details."
