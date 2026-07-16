# TAARS Phase-One Vertical Slice Breakdown

Status: proposed

Parent: [TAARS Portfolio AI Assistant PRD](./PRD.md)

This breakdown turns the phase-one PRD into tracer-bullet issues. Each slice delivers a narrow, demoable path through the required data model, application behavior, API, UI, and tests. Once approved, the slices will be published as individual local issues under `issues/` with `ready-for-agent` status.

## Proposed Slices

### 1. Publish One Experience and Answer with pgvector Evidence

**Blocked by:** None

**User stories covered:** 1, 3, 4, 23, 26, 29, 33-36, 87, 90, 92, 101-103

Establish the first complete tracer path: create a minimal owner profile and experience in the Profile UI, persist canonical data in PostgreSQL, publish it, index it through the PostgreSQL/pgvector backend, ask a question in the widget, and receive a grounded answer with expandable evidence references.

This slice also establishes the application seams that later slices extend: canonical profile storage, published snapshots, normalized evidence candidates, retrieval backend selection, the answer engine, and one complete chat turn.

### 2. Make Profile Publication Versioned and Recoverable

**Blocked by:** 1

**User stories covered:** 24-32, 47-50, 55

Extend the tracer path with draft isolation, minimum-profile validation, required month-and-year dates, explicit ongoing status, required qualitative outcomes, immutable published snapshots, backend indexing readiness, atomic activation, and rollback.

The currently published version remains answerable while a new version is being validated and indexed. Invalid or incomplete items cannot enter a published snapshot.

### 3. Connect Projects and Skills Through Demonstrated Evidence

**Blocked by:** 2

**User stories covered:** 5, 6, 8-11, 39, 51-52

Add project and skill management to the Profile UI and canonical model. Projects exist independently and can link to experiences or education. Skills are normalized with owner approval and explicitly connected to the work that demonstrates them.

Visitors can ask about a project or skill and receive answers grounded in the relevant contribution, qualitative outcome, optional verified metrics, technologies, and linked experience evidence.

### 4. Answer Career Chronology Across Organizations, Roles, and Education

**Blocked by:** 2

**User stories covered:** 7, 22, 38, 40, 47-48, 53-54

Add canonical organizations, separate role records for promotions, visual grouping by organization, education entries, and explicit current or ongoing status.

Visitors can ask about the current role, a historical role, education, or overall career chronology. Retrieval returns representative evidence across the requested timeline instead of allowing the newest item to crowd out relevant history.

### 5. Let Owners Control Emphasis and Public Visibility

**Blocked by:** 3, 4

**User stories covered:** 12, 14-22, 37, 55, 78

Complete the phase-one Profile view with achievements, approved personal topics, per-item visibility, featured state, public display rank, and answer priority.

Broad questions reflect owner-selected emphasis, while explicit questions continue to prefer the most relevant evidence. Private information is excluded before indexing. Display order and answer priority have linked defaults but remain independently editable.

### 6. Preserve Conversation Continuity and Expose Transcripts

**Blocked by:** 1

**User stories covered:** 43-46, 57-63, 80, 82, 105

Store each completed visitor and assistant message as an immutable row linked to a conversation. Maintain bounded recent context, a running summary, active topics, and resolved references without resending the entire transcript on every turn.

Add the Conversations dashboard view with ordered transcript display, pagination or incremental loading, search, answer status, profile version, retrieval backend, and supporting evidence. Visitor statements remain conversation context and never become owner-profile facts.

### 7. Turn Unsupported Questions into Actionable Content Gaps

**Blocked by:** 5, 6

**User stories covered:** 41-42, 64-69, 73, 79

Implement `SUPPORTED`, `PARTIAL`, and `UNANSWERABLE` answer outcomes across retrieval, answer generation, transcript storage, and UI presentation.

Cluster legitimate unsupported questions into content gaps, record only the unsupported portion of partial questions, link gaps to relevant profile items, track frequency and session intent, and expose an actionable Content Gaps dashboard view.

### 8. Reject Unrelated and Adversarial Use Without Polluting Gaps

**Blocked by:** 7

**User stories covered:** 56, 69, 83-86

Add deterministic input and output limits, scope enforcement, prompt-injection defenses, untrusted-profile-content handling, and tool-free bounded generation.

Benign out-of-scope, adversarial, spam, and resource-abuse requests receive cheap bounded responses and separate security events. They do not create content gaps or profile recommendations.

### 9. Evaluate Publication and Surface Assistant Quality

**Blocked by:** 5, 7, 8

**User stories covered:** 30-32, 61, 73, 81, 96-99, 104

Generate profile-specific evaluation cases for direct facts, chronology, relationships, partial answers, legitimate abstention, private data, off-topic requests, and prompt injection.

Block publication on critical failures and expose lower-severity warnings. Add the Quality dashboard view with evidence recall, irrelevant-evidence rate, supported-claim rate, correct abstention, chronology accuracy, latency, token usage, estimated cost, and retrieval diagnostics.

### 10. A/B Test Cognee Against PostgreSQL/pgvector Retrieval

**Blocked by:** 9

**User stories covered:** 90-94, 97

Implement the Cognee knowledge backend against the same indexing and normalized evidence-candidate contract as PostgreSQL/pgvector.

Both variants receive the same published canonical snapshot and use the same answer engine, model, prompt policy, verification, and presentation. Assignment remains stable within a session, backend versions are recorded, and the Quality view compares retrieval correctness, chronology, latency, and cost without mixing ingestion differences into the experiment.

## Dependency Graph

```text
1 Minimal experience-to-answer tracer
├── 2 Versioned publication
│   ├── 3 Projects and skills
│   └── 4 Career chronology
│       └── 5 Emphasis and visibility
└── 6 Conversation continuity

5 + 6
└── 7 Content gaps
    └── 8 Scope and abuse controls

5 + 7 + 8
└── 9 Evaluation and quality
    └── 10 Cognee retrieval A/B
```

## Review Questions

1. Does the granularity feel right, or is any slice too coarse or too fine?
2. Are the dependency relationships correct?
3. Should any slices be merged or split before individual issue files are created?
