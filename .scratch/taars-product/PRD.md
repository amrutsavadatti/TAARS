# TAARS Portfolio AI Assistant

Status: ready-for-agent

This PRD captures the product decisions accepted during the initial TAARS grilling session and its first continuation. It is intentionally versionable: later grilling should update this document as additional decisions are made.

## Problem Statement

Portfolio websites present professional information as static pages, resumes, and project descriptions. Recruiters, team leads, and technical evaluators often need to understand a portfolio owner's story, current trajectory, relevant experience, skills, and project impact without knowing where that information appears or how the pieces connect.

The existing TAARS implementation attempts to solve this through document chunking and vector retrieval. That approach ranks mainly by semantic similarity. It does not model canonical facts, validity periods, currentness, source authority, owner-selected prominence, contradictions, or query-specific relevance policy. As a result, older or less important information can displace newer or more useful evidence, retrieval can include irrelevant chunks, and the answer model may receive conflicting or insufficient context.

The existing implementation is also not yet a multi-tenant product. API-key validation and owner resolution are placeholders, durable conversation storage uses a single-node prototype database, profile management is document-oriented rather than owner-reviewed and structured, and there is no substantive answer-quality evaluation suite.

Portfolio owners also lack feedback about what visitors want to know. Legitimate unanswered questions disappear into transcripts instead of becoming clustered content gaps. Owners cannot see which projects, skills, jobs, or stories attract interest, how visitor intent develops, or which conversations lead to a request for contact.

TAARS must become a trustworthy portfolio assistant that answers only from an owner-approved public profile, explains the owner without impersonating them, learns from legitimate visitor questions, preserves evidence for every answer, and resists unrelated or adversarial GPT use. The core data model remains ownership-aware, but hardened public multi-tenancy and visitor conversion are later phases.

## Solution

TAARS will provide an embeddable chat widget for portfolio websites. The assistant will clearly identify itself as an AI assistant and speak about the portfolio owner in the third person. It will answer recruiter, team-lead, developer, and other visitor questions using a versioned canonical profile created and published by the owner.

The pilot will start with structured profile forms rather than automatic document extraction. Owners will enter or paste information into repeatable forms for experiences, projects, education, skills, achievements, and explicitly allowed personal topics. There is no dedicated career-story section. Structured core fields make chronology and relationships deterministic, while optional narrative fields add detail to individual profile items.

Owners will control public visibility, display order, featured items, and answer emphasis. Display ordering and answer priority will be separate controls with linked defaults. Skills will be canonical entities explicitly connected to the experiences and projects that demonstrate them. Newly edited information will remain in a draft until the owner publishes a versioned snapshot. The live assistant will continue using the previous snapshot until the new one has passed validation and is published atomically.

PostgreSQL will be the durable system of record for tenants, profiles, profile versions, canonical claims, evidence, visitors, consent, sessions, individual messages, classifications, content gaps, model usage, and analytics. pgvector will provide one retrieval implementation. Cognee will provide a second implementation behind a TAARS-owned `KnowledgeBackend` contract. Both backends will index the same published canonical snapshot and return a normalized evidence-candidate format. TAARS will own final ranking, generation, answer verification, and analytics.

Retrieval A/B testing and ingestion benchmarking will be separate experiments. Live A/B tests will initially compare retrieval only: the same approved profile, question, answer model, and answer policy will be used for both backends. Future document-ingestion systems will be evaluated offline by comparing proposed structured facts with owner-approved ground truth.

TAARS will distinguish supported, partially supported, and unanswerable questions. It will answer only the supported portion of a partial question and record the missing portion as a content gap. Legitimate gaps will be clustered and linked to relevant profile items so the owner can add targeted information. Off-topic, adversarial, spam, and resource-abuse events will be recorded separately and will not pollute content recommendations.

Visitor-facing answers are concise by default, expand when the question calls for detail, and may use sanitized structured formatting for lists, comparisons, and timelines. Each answer exposes compact, expandable references to the owner-approved profile evidence that supports it. Raw retrieval scores and internal diagnostics remain dashboard-only.

All conversations are stored as immutable sequences of individual messages and made visible to the portfolio owner. The full transcript is durable, but answer generation uses a bounded recent-message window plus a running conversation summary. Derived classifications, summaries, content gaps, and analytics remain separate and recomputable.

Phase one is a single-owner or trusted internal pilot that remains structurally ownership-aware. It focuses on profile building, profile publication, PostgreSQL/pgvector and Cognee retrieval, response quality, content gaps, conversation storage, and the owner dashboard. Production owner authentication, public multi-tenant isolation, OTP identity gates, visitor conversion, scheduling, and outreach are deferred until the assistant experience is refined. A later validation phase may expand to 10 to 25 owners after isolation is implemented.

## User Stories

1. As a portfolio owner, I want to create a TAARS profile, so that visitors can learn about my professional background conversationally.
2. As a portfolio owner, I want an optional AI-generated professional headline that I can approve or reject, so that a headline is available without becoming required profile work.
3. As a portfolio owner, I want to add multiple work experiences, so that TAARS can explain my career history.
4. As a portfolio owner, I want each experience to include company, title, start month and year, end month and year or current status, summary, outcome, achievements, skills, and links, so that chronology and context are explicit.
5. As a portfolio owner, I want to add multiple projects, so that visitors can explore the work I am proud of.
6. As a portfolio owner, I want each project to capture its problem, my contribution, required qualitative outcome, optional measurable impact, technologies, dates, collaborators, and links, so that TAARS can answer detailed project questions without pressuring me to invent metrics.
7. As a portfolio owner, I want to add education entries, so that TAARS can explain my academic background accurately.
8. As a portfolio owner, I want to maintain a canonical skill list, so that equivalent spellings do not fragment my profile.
9. As a portfolio owner, I want to approve suggested skill normalization, so that TAARS never silently changes the meaning of my profile.
10. As a portfolio owner, I want to connect skills to experiences and projects, so that TAARS can explain where and how I used them.
11. As a portfolio owner, I want to add context and evidence for a skill, so that TAARS does not infer proficiency from a skill name alone.
12. As a portfolio owner, I want to add achievements and proud moments, so that broad questions emphasize work that represents me well.
13. As a portfolio owner, I want to add narrative detail alongside structured fields, so that accurate answers still convey my story and personality.
14. As a portfolio owner, I want to enable selected personal categories such as hobbies or interests, so that TAARS can discuss only the personal information I intend to make public.
15. As a portfolio owner, I want sensitive categories blocked by default, so that uploading or entering information does not automatically make it answerable.
16. As a portfolio owner, I want to set visibility on every profile item, so that private information never reaches public retrieval.
17. As a portfolio owner, I want to rearrange projects, experiences, skills, and achievements within their categories, so that my public profile reflects my preferred presentation.
18. As a portfolio owner, I want public display order and assistant answer priority to be separate controls, so that visual presentation does not override factual relevance.
19. As a portfolio owner, I want linked defaults for display order and answer priority, so that common profile editing remains simple.
20. As a portfolio owner, I want to feature selected profile items, so that broad questions prioritize work I consider important.
21. As a portfolio owner, I want explicit questions to override my editorial ranking, so that TAARS still retrieves an older but directly relevant project or skill.
22. As a portfolio owner, I want currentness recorded independently from importance, so that current-role questions and proudest-achievement questions can rank differently.
23. As a portfolio owner, I want my profile edits saved as a draft, so that incomplete changes do not affect the live assistant.
24. As a portfolio owner, I want to preview additions, changes, removals, and conflicts before publishing, so that I remain responsible for canonical truth.
25. As a portfolio owner, I want material conflicts and high-importance facts brought to my attention, so that contradictory profile information is not silently resolved by retrieval scores.
26. As a portfolio owner, I want to publish a versioned profile snapshot atomically, so that the assistant never serves a partially indexed profile.
27. As a portfolio owner, I want the previous published profile to remain live while a new version is processed, so that profile maintenance does not cause downtime.
28. As a portfolio owner, I want to roll back to an earlier published version, so that an incorrect publication can be reversed quickly.
29. As a portfolio owner, I want every answer tied to the profile version used, so that I can reproduce and debug historical behavior.
30. As a portfolio owner, I want profile-specific evaluation results before publication, so that critical answer failures are found before visitors see them.
31. As a portfolio owner, I want critical failures to block publication, so that cross-tenant data, private facts, or invented employment never go live knowingly.
32. As a portfolio owner, I want lower-severity evaluation failures shown as warnings, so that I can make an informed publication decision.
33. As a visitor, I want the widget to disclose that it is an AI assistant, so that I am not misled into believing I am directly messaging the portfolio owner.
34. As a visitor, I want TAARS to speak about the owner in the third person, so that its identity remains unambiguous throughout the conversation.
35. As a visitor, I want to ask about the owner's experiences, projects, education, skills, achievements, and approved personal interests, so that I can evaluate relevant fit efficiently.
36. As a visitor, I want concise evidence-grounded answers, so that I can trust the assistant without reading the entire portfolio.
37. As a visitor, I want broad questions to reflect the owner's featured work, so that the answer represents what the owner considers important.
38. As a visitor, I want current-role questions to prioritize current facts, so that outdated experience is not presented as the present state.
39. As a visitor, I want skill questions to include concrete examples, so that I can distinguish demonstrated experience from keyword listing.
40. As a visitor, I want career-trajectory questions to cover representative points across time, so that recent items do not crowd out the full story.
41. As a visitor, I want TAARS to answer the supported part of my question and identify what it does not know, so that partial evidence does not become a fabricated complete answer.
42. As a visitor, I want a clear fallback when TAARS cannot answer, so that uncertainty is honest rather than hidden.
43. As a visitor, I want TAARS to answer my question before asking about me, so that the conversation provides value before requesting engagement.
44. As a visitor, I want follow-up questions to be optional and limited, so that the assistant feels conversational rather than interrogative.
45. As a visitor, I want TAARS to connect my interests to a real parallel in the owner's profile, so that the conversation becomes personally relevant without inventing similarities.
46. As a visitor, I want TAARS to avoid forcing a parallel when none is supported, so that friendly conversation remains trustworthy.
47. As a portfolio owner, I want every experience, project, and education entry to require at least a start month and year, so that chronological answers use explicit dates.
48. As a portfolio owner, I want every dated item to require an end month and year or explicit ongoing status, so that a missing date is never mistaken for current work.
49. As a portfolio owner, I want a qualitative outcome required for experiences and projects, so that TAARS can explain what changed because of my work.
50. As a portfolio owner, I want numeric metrics to remain optional, so that I do not need to invent unsupported measurements.
51. As a portfolio owner, I want projects to exist independently from work experiences, so that professional, side, academic, open-source, and cross-role projects use one canonical record.
52. As a portfolio owner, I want to link a project to experiences or education entries, so that TAARS can explain the context in which the work occurred.
53. As a portfolio owner, I want each role or promotion at an organization stored separately, so that titles, dates, outcomes, and skills do not become mixed.
54. As a portfolio owner, I want multiple roles visually grouped under the same organization, so that career progression remains easy to scan.
55. As a portfolio owner, I want to publish without a career story, headline, or suggested questions, so that structured professional information is sufficient to launch the assistant.
56. As a visitor, I want unrelated or adversarial requests rejected cheaply, so that TAARS remains focused on the portfolio owner.
57. As a portfolio owner, I want every visitor conversation stored and ordered correctly, so that I can review the exact interaction later.
58. As a portfolio owner, I want user and assistant messages stored individually under a conversation, so that transcripts can be paginated, searched, classified, and analyzed.
59. As a portfolio owner, I want to search conversation text, so that I can find discussions about a project, skill, role, or recurring concern.
60. As a portfolio owner, I want to see which profile evidence supported each assistant answer, so that I can investigate mistakes and improve my profile.
61. As a portfolio owner, I want model, token, latency, answer-status, and backend information recorded for each answer, so that quality and cost can be analyzed.
62. As a portfolio owner, I want derived summaries and classifications stored separately from original messages, so that analytics can improve without rewriting transcript history.
63. As a portfolio owner, I want conversations to be immutable during normal product use, so that the historical record cannot be selectively edited.
64. As a portfolio owner, I want legitimate unanswered questions clustered into content gaps, so that repeated visitor needs become actionable profile improvements.
65. As a portfolio owner, I want a content gap linked to the relevant project, experience, skill, or profile section, so that I can add information in the correct place.
66. As a portfolio owner, I want each gap to identify the unsupported portion of a partial question, so that useful existing answers are not mislabeled as complete failures.
67. As a portfolio owner, I want occurrence counts and trends for content gaps, so that I can prioritize improvements with recurring demand.
68. As a portfolio owner, I want to know when a gap appears in a high-intent session, so that important missing content receives attention.
69. As a portfolio owner, I want abuse and off-topic events excluded from content gaps, so that attackers cannot manipulate my profile recommendations.
70. As a portfolio owner, I want analytics grouped by projects, skills, jobs, education, achievements, and story topics, so that I know what attracts visitor attention.
71. As a portfolio owner, I want to see topic trends over time, so that I can understand changing interest in my background.
72. As a portfolio owner, I want to see which questions and profile evidence recur in high-intent sessions, so that I can understand what creates qualified interest.
73. As a portfolio owner, I want to see answers that produced repeated clarification questions, so that I can identify ambiguous or incomplete profile content.
74. As a portfolio owner, I want visitor sessions classified by behavioral intent, so that I can distinguish hiring evaluation, technical evaluation, collaboration, networking, research, casual browsing, and unknown intent.
75. As a portfolio owner, I want intent classification to be multi-label and confidence-scored, so that a technical evaluator who may also be hiring is not forced into one identity label.
76. As a portfolio owner, I want the behavioral evidence behind an intent classification, so that analytics labels are explainable.
77. As a visitor, I want intent inference used only for relevant conversational follow-ups and aggregate analytics, so that TAARS does not pretend to know my identity or restrict access.
78. As a portfolio owner, I want a Profile dashboard view, so that I can create, order, validate, and publish my structured profile.
79. As a portfolio owner, I want a Content Gaps dashboard view, so that I can turn clustered unanswered questions into profile improvements.
80. As a portfolio owner, I want a Conversations dashboard view, so that I can search and inspect complete stored transcripts and the evidence used.
81. As a portfolio owner, I want a Quality dashboard view, so that I can inspect unsupported-answer events, retrieval diagnostics, profile health, latency, and cost.
82. As a visitor, I want TAARS to remember recent context and summarized earlier context within my session, so that follow-up questions remain coherent without sending the entire transcript to the model.
83. As a platform operator, I want questions and visitor identity sent in request bodies rather than URL query parameters, so that sensitive content is less likely to leak through URL logging.
84. As a platform operator, I want uploaded and owner-entered content treated as untrusted data, so that embedded instructions cannot override TAARS control policy.
85. As a platform operator, I want answer generation to have no general-purpose tools and a fixed output budget, so that visitors cannot repurpose TAARS as unrestricted GPT access.
86. As a platform operator, I want unsupported claims detected before or after generation, so that retrieval relevance alone is not mistaken for answer grounding.
87. As a platform operator, I want PostgreSQL to be the durable source of truth, so that tenant data, conversations, evidence, and analytics share transactional integrity.
88. As a platform operator, I want transient rate counters, working summaries, and caches kept outside durable conversation records, so that ephemeral state has appropriate lifecycle controls.
89. As a platform operator, I want original future uploads stored as objects rather than database message blobs, so that document storage and relational data can scale independently.
90. As a platform operator, I want pgvector and Cognee behind the same retrieval contract, so that backend experiments do not alter product behavior.
91. As a platform operator, I want stable session-level A/B assignment, so that one visitor does not switch retrieval backends midway through a conversation.
92. As a platform operator, I want every retrieval result normalized into evidence candidates, so that ranking and generation remain backend-independent.
93. As a platform operator, I want Cognee to return context or raw retrieval objects rather than a final answer, so that answer-generation differences do not confound retrieval tests.
94. As a platform operator, I want ingestion and retrieval experiments separated, so that extraction errors are not attributed to retrieval quality.
95. As a platform operator, I want future file extraction to propose form changes rather than mutate canonical truth, so that owner review remains the authority boundary.
96. As a product team, I want profile-specific and shared adversarial evaluation suites, so that quality can be measured consistently across tenants and backend versions.
97. As a product team, I want retrieval evidence coverage, irrelevant-evidence rate, supported-claim rate, correct abstention, chronology accuracy, latency, and cost measured, so that backend selection is evidence based.
98. As a product team, I want live conversion analytics treated separately from retrieval correctness, so that a persuasive but inaccurate backend cannot win solely on engagement.
99. As a product team, I want the pilot constrained to a small validation cohort, so that product trust and usefulness are proven before optimizing for large scale.
100. As a future maintainer, I want pinned and deferred decisions recorded explicitly, so that later work does not silently assume unresolved requirements.
101. As a visitor, I want compact expandable references on each answer, so that I can inspect the owner-approved profile evidence without seeing internal retrieval scores.
102. As a visitor, I want answers to be concise by default and expand for lists, timelines, comparisons, or explicit detail requests, so that the conversation remains easy to scan.
103. As a visitor, I want safe bullets and short headings when they improve comprehension, so that complex professional information is not forced into dense prose.
104. As a portfolio owner, I want the assistant to treat useful supported answers as the primary success signal, so that identity capture never becomes more important than answer quality.
105. As a platform operator, I want conversation memory separate from owner-profile retrieval, so that visitor statements cannot enter the owner's canonical knowledge base.

## Implementation Decisions

- TAARS is designed to become a multi-tenant portfolio AI assistant for recruiters, team leads, developers, collaborators, and other portfolio visitors. Phase one runs as a single-owner or trusted internal pilot.
- The primary product job is to help visitors understand the portfolio owner's experiences, projects, skills, education, achievements, and approved personal context.
- Secondary product jobs are to learn from legitimate visitor questions, identify content gaps, classify session intent, provide profile analytics, and support voluntary contact conversion.
- TAARS must always identify itself as an AI assistant. It speaks about the portfolio owner in the third person and never impersonates the owner.
- The pilot profile experience is form-first. Automatic parsing of PDF, DOCX, images, resumes, or LinkedIn data is not required for the initial version.
- Future ingestion pipelines populate proposed form values. They never bypass validation, owner review, or the canonical profile repository.
- Owner-entered form values are treated as owner-verified canonical information once published.
- Phase-one profile categories include experiences, projects, education, skills, achievements, and owner-approved personal topics. There is no dedicated career-story section.
- A professional headline is optional. TAARS may generate a draft headline from published profile information, but the owner must approve it before use.
- Suggested visitor questions are not required and are not part of phase one.
- A profile may be published when it has an owner name, at least one valid experience or project, and no published item with missing required fields.
- Each profile item combines structured core fields with optional narrative detail.
- Experiences explicitly model organization, title, start month and year, end month and year or current status, optional location, summary, required qualitative outcome, achievements, skills, links, visibility, featured state, display rank, and answer priority.
- Each promotion or materially different role is a separate experience linked to a canonical organization. The UI may group roles by organization.
- Projects explicitly model the problem, owner contribution, required qualitative outcome, optional measurable impact, technologies, start month and year, end month and year or ongoing status, collaborators, links, visibility, featured state, display rank, and answer priority.
- Projects are independent canonical items with optional links to one or more experiences or education entries.
- Education entries require at least a start month and year plus an end month and year or ongoing status.
- Missing end dates never imply current or ongoing status; currentness is explicit.
- Skills are canonical per owner. Owners approve normalization and aliases, then explicitly link skills to experiences and projects.
- Skill relationships may include context, evidence, last-used date, and an owner-selected depth descriptor. Answers prefer demonstrated evidence over unsupported proficiency labels.
- Owner-controlled topic allowlists determine which personal categories can be answered. Sensitive categories are blocked by default.
- Every canonical item has an explicit visibility state. Private data is excluded before indexing, not filtered only at final generation.
- Public display rank, featured status, and answer priority are separate fields. The UI may update them together by default, but owners can separate them.
- Owner answer priority is a bounded ranking signal. It may break close relevance scores but cannot override a clearly explicit question.
- Ranking is query-dependent and considers semantic or lexical relevance, currentness when implied, owner-selected prominence, verified outcomes, source authority, fact confidence, requested chronology, and visibility.
- Currentness and importance are independent. Older facts remain retrievable when explicitly relevant.
- Profile changes follow a draft, validate, review, publish workflow.
- Published profiles are immutable versioned snapshots. Publication atomically changes the snapshot used by the live assistant and both retrieval indexes.
- The previous published profile stays live while new indexing and evaluation run. Rollback to a prior version is supported.
- Conflicting or materially important future extracted claims require owner review. Until resolution, disputed details are omitted or explicitly treated as uncertain.
- Canonical facts preserve subject, predicate, value, validity interval, currentness, importance, visibility, source evidence, and owner-verification metadata where applicable.
- PostgreSQL is the durable system of record for ownership-aware profiles, profile versions, canonical facts, relationships, conversations, messages, answer evidence, classifications, gaps, usage, and analytics. Visitor identity and consent tables are added when the deferred identity phase begins.
- pgvector is installed in the same PostgreSQL system for the pilot retrieval implementation.
- Redis or Valkey holds temporary session state, rate counters, working summaries, and caches. Future OTP challenges also belong in ephemeral storage and are never stored as plaintext durable records.
- Future original documents live in object storage, while metadata and proposed facts live in PostgreSQL.
- Core durable records and adapter calls carry an owner identifier so future tenant isolation does not require a data-model rewrite. Production authentication, row-level security, and public multi-tenant authorization are deferred.
- Conversations and messages have a one-to-many relationship. Each user or assistant message is stored once as a completed immutable row, not once per streamed token and not inside one growing conversation JSON blob.
- Message ordering is explicit and unique within a conversation.
- Assistant message records include or link to profile version, answer status, model, retrieval backend and version, token usage, cost inputs, latency, and supporting evidence.
- Supporting evidence is stored through separate answer-evidence links to canonical claims and source excerpts.
- Visitor-facing answers show compact, expandable references to owner-approved profile items or excerpts. Raw similarity scores and retrieval diagnostics remain owner-facing.
- Derived summaries, topic labels, intent classifications, gap clusters, and future model outputs remain separate from immutable original messages and can be recomputed.
- Portfolio owners can view and search their conversations. Transcript editing is not supported during normal product use.
- Raw-transcript retention duration is unresolved. Administrative visitor deletion or anonymization tooling is deferred, but stable identity relationships should keep the schema compatible with future privacy workflows.
- The durable chat API uses request bodies and a streaming response mechanism. Questions, email addresses, names, and other visitor data are not placed in URL query parameters.
- Owner login, public widget identifiers, origin allowlists, OTP verification, visitor follow-up consent, verified question allowances, scheduling, and outreach are accepted future directions but are deferred from phase one.
- TAARS separates benign in-scope, ambiguous, benign out-of-scope, adversarial, and resource-abuse handling.
- Deterministic controls run before model calls wherever possible. Scope classification and retrieval gates prevent unnecessary answer-model usage.
- Uploaded, pasted, and owner-entered content is untrusted data and cannot supply control instructions to the answer model.
- The visitor-facing answer model receives no general-purpose tools and has fixed input and output budgets.
- Answers are usually two to four sentences. They expand when the visitor requests detail or when a list, comparison, or timeline requires it.
- The widget renders a restricted sanitized Markdown subset. Plain prose is preferred for normal answers; bullets and short headings are allowed when they improve scanning.
- The answer pipeline produces `SUPPORTED`, `PARTIAL`, or `UNANSWERABLE` outcomes.
- A partial answer contains only supported information, states its limitation, and logs the unsupported portion as a gap.
- An unanswerable legitimate in-scope question returns a concise fallback and creates or increments a clustered gap.
- Off-topic, injection, spam, and resource-abuse events are security analytics, not content gaps.
- Content-gap records preserve the normalized question, topic, linked profile item, missing information, relevant retrieval evidence, session intent, and frequency.
- Similar gaps are clustered so owners see demand patterns rather than duplicated raw questions.
- Session classification represents behavioral intent, not asserted visitor identity.
- Initial intent labels are hiring evaluation, technical evaluation, project collaboration, professional networking, learning or research, casual browsing, and unknown.
- Sessions can carry multiple intent labels with confidence and supporting behavioral evidence.
- In phase one, intent may influence one optional follow-up question and analytics organization. It does not restrict information or assert who the visitor is. Contact calls to action are a later phase.
- TAARS may ask one optional conversational follow-up after answering. It can draw a parallel to the owner's profile only when supported by retrieved evidence.
- Visitor disclosures remain session data and are never added to the owner's canonical knowledge base automatically.
- The complete conversation is persisted, but generation uses a bounded recent-message window, a running summary, resolved references, and active topics rather than resending the full transcript.
- `ConversationMemory` is separate from `KnowledgeBackend`. Phase one uses deterministic recent-window plus summary memory.
- Cognee conversation memory is a future `ConversationMemory` adapter and is evaluated separately from profile retrieval. Any automatic bridge from visitor session memory into the permanent owner graph must remain disabled.
- `CanonicalProfileRepository` owns drafts, published snapshots, and canonical facts independently from retrieval technology.
- `SourceExtractor` is the future ingestion seam that converts a source into proposed canonical changes and evidence.
- `KnowledgeBackend` is the retrieval/indexing seam. It indexes or removes published snapshots, reports readiness, and retrieves normalized evidence candidates.
- Initial knowledge backend implementations are PostgreSQL/pgvector and Cognee.
- Both knowledge backends index the same owner-approved published snapshot.
- Knowledge backends return normalized evidence candidates containing canonical claim and source identities, text, relevance, validity, currentness, owner priority, source authority, and backend metadata.
- TAARS owns final ranking after backend retrieval so product policy remains consistent across implementations.
- Cognee is used for retrieval context or raw objects in the live experiment. Cognee does not own canonical truth and does not produce the final visitor answer during the retrieval A/B test.
- `AnswerEngine` receives normalized evidence, constructs the bounded response, and verifies support independently of the retrieval backend.
- Retrieval A/B assignment is stable for a session and recorded with backend and configuration versions.
- The first live A/B test compares retrieval only. Both variants use the same canonical profile, question, answer engine, answer model, prompts, verification rules, and limits.
- Ingestion comparison is an offline benchmark against owner-approved structured ground truth. Extraction variants are not mixed into live retrieval experiments.
- Phase one targets one owner or a trusted internal environment while preserving ownership-aware records. A later isolated validation cohort may target 10 to 25 owners, 20 to 200 canonical facts per owner, and about 1,000 total visitor sessions per month.
- Phase-one success is determined first by supported useful answers, then relevant multi-topic exploration, actionable gaps, chronology quality, acceptable latency, and bounded cost. Email verification, follow-up requests, and meeting conversion become later success signals when those features exist.
- The phase-one owner dashboard has four views: Profile, Content Gaps, Conversations, and Quality.
- The Profile view creates, edits, orders, validates, and publishes profile items.
- The Content Gaps view prioritizes clustered legitimate unanswered questions and links them to profile items.
- The Conversations view searches and displays immutable transcripts, answer status, topics, and supporting evidence.
- The Quality view shows unsupported-answer events, retrieval diagnostics, profile health, latency, token usage, and cost.
- Owner-configurable personality, tone, detail, and proactivity controls are deferred. Phase one uses one platform-defined professional and friendly style.
- Visitor answer-rating controls, interactive draft-profile chat preview, and optional AI rewriting of form content are deferred.
- The existing application is an implementation reference, not a constraint that preserves placeholder authentication, global owner settings, document-first ingestion, ChromaDB, or SQLite.

## Testing Decisions

- Tests assert externally visible behavior rather than private method calls, prompt text, database query shape, or third-party implementation details.
- The primary chat test seam is one complete visitor turn through a chat application service with fake profile, retrieval, conversation-memory, answer, safety, and transcript ports. This seam verifies the largest meaningful phase-one behavior with the fewest mocks.
- The second primary seam is profile publication from an owner draft to an immutable published snapshot and ready retrieval indexes. It verifies validation, versioning, publication blocking, backend indexing, atomic activation, and rollback behavior.
- Both knowledge backends share one contract-test suite. Given the same published fixture and query, each must return normalized evidence candidates scoped to the correct tenant and traceable to canonical claims.
- Retrieval quality tests use profile-specific fixtures and assert evidence identities or supported facts, not exact floating-point scores.
- Answer tests assert that every factual claim is supported by returned evidence, private facts are absent, and unsupported details cause partial or unanswerable behavior.
- Answer presentation tests assert concise adaptive length, sanitized structured formatting, and compact evidence references without raw retrieval scores.
- Chronology tests cover current-role questions, historical skill usage, career trajectories, overlapping dates, missing end dates, and older explicitly requested projects.
- Ranking tests verify that explicit query relevance overrides display rank while owner priority influences broad or ambiguous questions.
- Content-gap tests verify clustering, frequency increments, partial-gap extraction, profile-item linkage, and exclusion of off-topic or adversarial traffic.
- Session-intent tests assert multi-label behavioral output, confidence, evidence, and the rule that inferred intent never becomes verified identity.
- Abuse tests cover oversized input, output-budget enforcement, rapid requests, concurrent sessions, repeated rejected requests, tenant budget exhaustion, off-topic prompts, prompt injection, and malicious instructions embedded in profile content.
- Ownership-scoping contract tests assert that repositories and adapters accept and preserve owner identifiers, even though hardened public tenant-isolation tests belong to the later multi-tenant phase.
- Conversation tests assert one durable row per completed message, deterministic ordering, transcript pagination, streaming finalization, evidence linkage, bounded recent context, running-summary updates, and recomputable derived analytics.
- Publication tests assert minimum-profile validation, month-and-year date requirements, explicit ongoing status, required qualitative outcomes, draft isolation, index readiness, atomic activation, evaluation blocking, and rollback.
- A/B infrastructure tests assert stable session assignment, identical generation configuration across retrieval variants, complete experiment logging, and exclusion of ingestion differences from the retrieval experiment.
- The automated evaluation corpus includes direct facts, currentness, chronology, relationships, broad story questions, supported partial questions, legitimate unanswerable questions, off-topic questions, prompt injection, and resource abuse.
- Evaluation metrics include evidence recall, irrelevant-evidence rate, supported-claim rate, correct abstention, partial-answer correctness, chronology accuracy, latency, token usage, and estimated cost.
- Conversion and engagement metrics are reported alongside but never substitute for correctness and grounding metrics.
- Critical publication failures include wrong-owner retrieval, private-data disclosure, invented employment or education, unsupported material claims, missing required dates or outcomes, and broken evidence references.
- Existing repository tests provide no substantive prior art beyond current module boundaries. New tests should establish behavior at the chat and publication seams rather than replicate the current placeholder implementation.

## Out of Scope

- Automatic PDF, DOCX, image, resume, or LinkedIn ingestion for the first pilot.
- Allowing an ingestion model to publish extracted facts without owner review.
- A required professional summary, career-story section, professional headline, or suggested visitor questions.
- General AI rewriting, completion, or achievement extraction inside profile forms. The only accepted narrow exception is an optional owner-approved generated headline.
- Selecting a specific meeting or scheduling provider.
- Deep scheduling API integration or emailing meeting links.
- Automated outreach campaigns and campaign-management UI.
- Treating OTP verification as marketing or outreach consent.
- Visitor name capture, email capture, OTP verification, follow-up consent, and verified daily allowances in phase one.
- Production owner authentication, billing, subscriptions, row-level security, public multi-tenant onboarding, widget-ID rotation, and origin-management UI in phase one.
- Visitor transcript editing or selective message redaction during normal product use.
- Implementing administrative visitor privacy deletion or anonymization workflows in the first pilot.
- Finalizing raw-transcript retention duration.
- General-purpose GPT access, web browsing, code execution, external tools, or answers unrelated to the portfolio owner.
- Automatically adding visitor statements to the owner's canonical profile.
- Using inferred visitor intent as verified identity or restricting access based on inferred class.
- Cognee owning canonical truth or generating the final answer in the initial retrieval A/B test.
- Cognee session memory in phase one or any automatic bridge from visitor conversations into the owner's permanent knowledge graph.
- Live A/B testing of unreviewed ingestion pipelines.
- A universal global impact score that overrides query intent.
- Owner-configurable assistant personality, tone, response detail, or proactivity controls.
- Visitor answer ratings and feedback controls.
- Interactive chat preview against draft profiles or side-by-side retrieval backend previews.
- Large-scale graph infrastructure adopted solely for anticipated future volume.
- Scaling beyond the initial validation cohort before trust, quality, and conversion hypotheses are measured.

## Further Notes

- Scheduling is deliberately provider-agnostic and pinned for later discussion. The future profile may store a validated HTTPS booking URL without requiring a provider-specific API.
- Outreach campaigns are pinned for a later dashboard PRD. Current consent covers only an optional conversation-specific follow-up by the portfolio owner.
- Privacy deletion and anonymization implementation is pinned. The data model should keep identity and derived-data relationships explicit so future administrative handling is possible without redesigning transcript storage.
- The accepted future identity flow allows four to five anonymous visitor questions, then requests email and optional conversation-specific follow-up consent, verifies by OTP, and permits up to 40 verified visitor questions per day. This complete flow is deferred from phase one.
- The accepted future widget-security direction uses a public widget identifier, a separate private owner account, origin allowlists, identifier rotation, rate limits, and tenant budgets. Browser origin checks are not treated as the sole security boundary.
- Retention periods, geographic launch scope, and jurisdiction-specific privacy terms remain unresolved and require separate product and legal review.
- The term `portfolio owner` refers to the tenant user whose public profile TAARS represents.
- The term `visitor` refers to a person interacting with the embedded widget.
- The term `canonical profile` refers to owner-approved structured truth independent of any retrieval backend.
- The term `published profile snapshot` refers to an immutable, versioned canonical profile activated for public answering.
- The term `canonical claim` refers to an atomic evidence-backed fact with validity, visibility, and provenance metadata where applicable.
- The term `evidence candidate` refers to a backend-independent retrieval result linked to canonical claims and source excerpts.
- The term `content gap` refers only to missing support for a legitimate in-scope visitor question.
- The term `session intent` refers to confidence-scored behavioral categories inferred from a conversation, not the visitor's verified occupation or identity.
- The initial grilling session is concluded. Later grilling may address retention, production isolation, identity conversion, scheduling, pricing, and operations without reopening the accepted phase-one assistant scope unless explicitly requested.
