---
name: enterprise-chat-ui
description: Transforms and maintains this Enterprise RAG + Agentic AI Platform as a polished, production-grade modern AI chat application comparable in interaction quality to ChatGPT and Claude. Use this skill whenever modifying the frontend, chat experience, visual design, animations, responsive behavior, message rendering, conversation UX, agent activity UI, approval UI, citations, attachments, loading states, or frontend interaction patterns.
---

# Enterprise Chat UI Skill

## 1. Mission

The application is an enterprise-grade RAG + Agentic AI platform.

The frontend must feel like a premium, modern AI product rather than an administrative dashboard with a chat box.

The interaction quality should be comparable to products such as:

- ChatGPT
- Claude
- Perplexity
- modern enterprise AI assistants

Do NOT copy proprietary branding, logos, exact layouts, or visual identities.

Instead, adopt the best interaction principles:

- excellent typography
- generous spacing
- clear visual hierarchy
- fluid animations
- fast perceived performance
- excellent streaming behavior
- intuitive conversation management
- polished message rendering
- unobtrusive controls
- strong accessibility
- responsive layouts
- graceful loading and error states
- professional information density

The product must retain its enterprise identity through:

- RBAC
- secure document retrieval
- citations
- guardrails
- agent/tool activity
- approval workflows
- memory
- observability
- evaluation
- enterprise security

---

# 2. NON-NEGOTIABLE ARCHITECTURAL RULE

The frontend is a presentation and interaction layer.

NEVER weaken, bypass, remove, duplicate, or replace backend security/business logic merely to make the UI easier to implement.

Preserve the existing:

- authentication
- authorization
- RBAC
- document access controls
- retrieval pipeline
- hybrid retrieval
- reranking
- guardrails
- agent orchestration
- tool registry
- tool authorization
- risk policies
- human approval
- external actions
- workflows
- memory
- multi-agent orchestration
- evaluation
- observability
- background jobs
- production infrastructure

Frontend code must consume existing APIs and contracts.

Do not move authorization decisions into the browser.

Do not trust client-supplied:

- user roles
- permissions
- approval status
- tool risk
- document access
- agent identity
- tenant identity
- memory ownership

The backend remains authoritative.

---

# 3. DESIGN PHILOSOPHY

The interface should communicate:

"Simple on the surface, sophisticated underneath."

A first-time user should see an extremely simple chat experience.

Advanced enterprise capabilities should progressively reveal themselves when relevant.

Avoid:

- dashboard overload
- excessive cards
- excessive borders
- unnecessary gradients
- excessive glassmorphism
- noisy shadows
- giant hero sections
- decorative animations
- permanent technical metadata
- exposing internal implementation details
- chain-of-thought
- raw agent reasoning
- raw trace IDs
- internal database IDs
- backend stack terminology unless useful to the user

Prefer:

- clean surfaces
- subtle borders
- restrained shadows
- strong typography
- meaningful whitespace
- compact controls
- contextual disclosure
- smooth transitions
- predictable interaction patterns

---

# 4. GLOBAL VISUAL SYSTEM

Before making broad UI changes, inspect the existing frontend and identify:

- framework
- component library
- CSS architecture
- design tokens
- typography
- spacing system
- icon system
- animation library
- theme system
- routing
- state management
- API/data fetching
- streaming implementation

Reuse existing infrastructure where appropriate.

Do not introduce an additional UI framework if an existing one already serves the purpose.

Do not create duplicate component systems.

Establish centralized design tokens for:

- colors
- typography
- spacing
- radius
- shadows
- transitions
- z-index
- breakpoints

Prefer semantic tokens over hard-coded values.

Example conceptual tokens:

--background
--surface
--surface-muted
--surface-elevated
--border
--foreground
--foreground-muted
--accent
--success
--warning
--danger

Use the project's existing theming mechanism when available.

---

# 5. TYPOGRAPHY

Typography must be treated as a core part of the product.

Prioritize:

- readability
- hierarchy
- line-height
- paragraph spacing
- code readability
- citation readability
- message scanning

Chat responses should never look like raw API output.

Use:

- comfortable reading width
- consistent heading hierarchy
- readable body size
- restrained metadata sizing
- clear distinction between user and assistant content

Do not make all text bold.

Do not overuse uppercase labels.

---

# 6. APPLICATION SHELL

The primary application should follow a modern AI assistant structure:

------------------------------------------------
| Sidebar |              Main Chat             |
|         |                                     |
| New Chat|             Header                  |
| Search  |-------------------------------------|
| Chats   |                                     |
|         |         Conversation               |
|         |                                     |
|         |                                     |
|         |                                     |
|         |-------------------------------------|
| User    |          Composer                   |
------------------------------------------------

Desktop:

- collapsible sidebar
- persistent conversation list
- main chat workspace
- compact header
- bottom composer

Mobile:

- sidebar becomes drawer
- compact header
- full-width conversation
- composer remains accessible
- no horizontal overflow

---

# 7. SIDEBAR

The sidebar should feel like a modern AI application.

Required capabilities:

- New Chat
- conversation search
- conversation list
- recent conversations
- active conversation indicator
- rename conversation
- delete/archive where supported
- user/account area
- settings
- responsive collapse

Conversation list should support:

- smooth hover states
- active state
- contextual menu
- keyboard navigation
- truncation
- date grouping where useful

Avoid permanently visible destructive controls.

Show contextual controls on hover/focus.

Sidebar open/close transitions must be smooth.

Do not cause layout jumps.

---

# 8. CHAT HEADER

Keep the header intentionally minimal.

Depending on current conversation state, show:

- assistant/application identity
- model or mode when useful
- conversation title
- relevant security/status indicator
- optional controls

Do not turn the header into a technical dashboard.

---

# 9. EMPTY STATE

The empty state should feel premium.

It should communicate:

- what the assistant can do
- suggested tasks
- optional example prompts

Example categories:

- Search enterprise knowledge
- Analyze documents
- Research a topic
- Summarize information
- Compare policies
- Draft an email
- Schedule an event

Do not overwhelm users with 20 suggestions.

Use 3–6 useful suggestions.

Suggestions should be actionable and visually elegant.

---

# 10. MESSAGE SYSTEM

Messages are the most important UI element.

The message system must support:

- user messages
- assistant messages
- streaming
- markdown
- headings
- lists
- tables
- blockquotes
- links
- inline code
- code blocks
- citations
- source references
- tool activity
- agent activity
- approval requests
- errors
- retry
- regenerate
- copy
- edit where supported

Assistant responses should generally NOT be placed inside giant bordered cards.

Use a clean reading-oriented layout.

User messages may use a subtle differentiated surface.

Maintain a comfortable maximum reading width.

---

# 11. STREAMING

Streaming should feel immediate and polished.

Requirements:

- render tokens progressively
- avoid excessive layout shifting
- preserve scroll position intelligently
- auto-scroll while the user is near the bottom
- stop auto-scrolling when the user intentionally scrolls upward
- show a clear generation state
- support cancellation
- transition cleanly from streaming to completed state

Never display raw transport artifacts.

Do not expose internal streaming protocol details.

---

# 12. ASSISTANT PROCESSING STATE

Do NOT show fake "thinking" animations implying hidden chain-of-thought.

Instead show truthful activity.

Examples:

- Searching knowledge...
- Reviewing sources...
- Analyzing documents...
- Preparing response...
- Checking permissions...
- Waiting for approval...

These states must correspond to actual backend events where possible.

Never fabricate an activity state that did not occur.

---

# 13. AGENT ACTIVITY

The backend contains agents, tools, workflows, and multi-agent orchestration.

Expose useful progress without exposing chain-of-thought.

Good:

"Researching external sources"

"Searching enterprise documents"

"Comparing retrieved information"

"Preparing calendar event"

"Waiting for your approval"

Bad:

"Reasoning step 1..."

"Internal thought..."

"Chain of thought..."

"System prompt..."

"Agent hidden reasoning..."

Use expandable activity sections where useful.

Example:

┌──────────────────────────────────┐
│ ✓ Searched enterprise knowledge │
│ ✓ Reviewed 6 sources             │
│ ✓ Compared relevant policies     │
└──────────────────────────────────┘

Keep these visually secondary to the final answer.

---

# 14. TOOL ACTIVITY

Tool calls should be represented as user-friendly activities.

Examples:

Search:

🔎 Searching enterprise knowledge

Web:

🌐 Searching the web

Calendar:

📅 Preparing calendar event

Email:

✉ Preparing email

Calculator:

🧮 Calculating

Do not expose:

- internal tool class names
- raw JSON
- internal function signatures
- database identifiers
- internal trace IDs

Tool failures should be understandable:

"Web search failed. Try again."

rather than:

"ToolExecutor raised ToolExecutionError."

---

# 15. CITATIONS AND SOURCES

Enterprise RAG is a core feature.

Citations must feel first-class.

Support:

- inline citations
- source chips
- source cards
- expandable source previews
- document title
- relevant page/section when available

Example:

According to the security policy, production credentials must...

[Security Policy.pdf · p. 12]

The UI must never imply a citation exists when the backend did not provide one.

Citation data must come from the backend.

Do not invent sources.

---

# 16. SOURCE PANEL

Where appropriate, provide an expandable Sources section.

Example:

Sources
──────────────
Security Policy
Employee Handbook
Engineering Standards

Each source can expose:

- title
- document type
- page/section
- relevance information if already available
- open/view action if supported

Do not expose retrieval scores unless there is a strong user-facing reason.

---

# 17. COMPOSER

The composer should be one of the strongest components in the application.

Support where backend capability exists:

- multiline input
- Enter to send
- Shift+Enter for newline
- auto-resize
- send button
- stop generation button
- attachment button
- drag-and-drop
- keyboard focus
- disabled states
- loading state

The composer should remain visually anchored near the bottom.

Use subtle elevation/border treatment.

Avoid oversized input fields.

---

# 18. ATTACHMENTS

If file upload exists or is supported:

Show:

- file name
- file type
- size
- upload state
- success
- error
- remove action

Use compact attachment pills/cards.

Do not block the entire interface during a normal upload.

---

# 19. APPROVAL UI

Human approval is a critical enterprise capability.

Approval requests must be visually distinct but not alarming unless genuinely high-risk.

Example:

┌─────────────────────────────────────┐
│ Approval required                   │
│                                     │
│ Send email                          │
│ To: client@example.com              │
│ Subject: Project update             │
│                                     │
│ Risk: High                          │
│ Expires in 4 minutes                │
│                                     │
│ [Reject]              [Approve]     │
└─────────────────────────────────────┘

The frontend must never manufacture approval.

Approval actions must call the backend approval APIs.

Never allow:

"yes"

in normal chat text to automatically approve a sensitive action unless the backend explicitly defines that interaction as an authenticated approval mechanism.

---

# 20. ERROR STATES

Every meaningful asynchronous operation needs a graceful failure state.

Examples:

- failed message
- failed retrieval
- failed tool
- failed external provider
- expired approval
- permission denied
- network interruption
- session expiration
- background job failure

Provide:

- clear explanation
- retry when safe
- recovery path
- appropriate visual hierarchy

Never dump stack traces into the production UI.

---

# 21. BACKGROUND JOBS

The application supports long-running/background agent jobs.

The UI must communicate:

- queued
- running
- waiting for approval
- completed
- failed

Long-running jobs should not appear frozen.

Where possible, support:

- live progress
- reconnect/resume
- persistent status
- navigation away and return
- conversation state restoration

---

# 22. ANIMATION SYSTEM

Animations must communicate state and hierarchy.

Use animation for:

- sidebar open/close
- message appearance
- source expansion
- tool activity expansion
- approval card appearance
- modal/drawer transitions
- hover/focus feedback
- loading indicators
- streaming cursor/state
- toast notifications
- route transitions where appropriate

Animation principles:

- fast
- subtle
- intentional
- interruptible
- performant

Typical conceptual ranges:

Micro-interactions:
100–180ms

Small transitions:
180–250ms

Panels/drawers:
250–350ms

Avoid unnecessarily long animations.

Do not animate every element.

Avoid animation that interferes with reading.

Respect:

`prefers-reduced-motion`

When reduced motion is enabled:

- remove decorative movement
- reduce transitions
- retain essential state changes
- preserve usability

---

# 23. MICRO-INTERACTIONS

Use polished but restrained feedback:

- button hover
- active states
- copy confirmation
- send confirmation
- successful approval
- source expansion
- sidebar selection
- retry
- attachment upload
- streaming completion

Examples:

Copy button:

Copy → Copied ✓

Approval:

Approve → Approved ✓

Do not use excessive bouncing, shaking, glowing, or particle effects.

---

# 24. LOADING STATES

Never leave blank regions while waiting.

Use appropriate:

- skeletons
- shimmer only when justified
- spinners
- progress indicators
- activity labels

Loading UI should resemble the final layout where possible to minimize layout shift.

---

# 25. RESPONSIVE DESIGN

The application must work on:

- desktop
- laptop
- tablet
- mobile

Minimum requirements:

- no horizontal overflow
- readable messages
- usable composer
- accessible sidebar
- touch-friendly controls
- responsive source cards
- responsive tables/code blocks
- mobile-safe dialogs
- mobile-safe approval cards

Do not simply shrink the desktop layout.

Design mobile behavior intentionally.

---

# 26. ACCESSIBILITY

Target WCAG 2.2 AA-level practices where practical.

Ensure:

- keyboard navigation
- visible focus
- semantic HTML
- accessible labels
- sufficient contrast
- screen-reader-friendly controls
- correct dialog semantics
- correct button semantics
- no keyboard traps
- reduced motion support

Do not use icons without accessible labels when the meaning is not obvious.

---

# 27. DARK MODE

Dark mode should be a deliberate design system.

Do not simply invert colors.

Ensure:

- readable text
- restrained contrast
- distinguishable surfaces
- accessible borders
- readable code
- readable citations
- appropriate status colors

Light and dark themes should feel like the same product.

---

# 28. PERFORMANCE

Protect perceived and actual performance.

Avoid:

- unnecessary rerenders
- massive client bundles
- excessive animation
- unnecessary DOM complexity
- unoptimized images
- expensive layout calculations

Prefer:

- lazy loading
- virtualization where justified
- memoization where useful
- efficient streaming rendering
- stable keys
- minimal layout shifts

Do not prematurely optimize without evidence.

---

# 29. COMPONENT ARCHITECTURE

Prefer reusable components.

Conceptual structure:

components/
  chat/
    ChatShell
    ChatHeader
    MessageList
    Message
    UserMessage
    AssistantMessage
    StreamingMessage
    MessageActions
    Composer
    EmptyState

  sources/
    Citation
    SourceList
    SourceCard
    SourcePreview

  agents/
    AgentActivity
    ToolActivity
    WorkflowProgress
    AgentStatus

  approvals/
    ApprovalCard
    ApprovalStatus

  conversations/
    ConversationSidebar
    ConversationItem
    ConversationSearch

  ui/
    Button
    Dialog
    Drawer
    Tooltip
    Toast
    Skeleton

Adapt to the actual project's architecture.

Do not blindly create these directories if equivalent structures already exist.

---

# 30. STATE MANAGEMENT

Do not introduce redundant state systems.

Inspect the current application first.

Clearly separate:

- server state
- conversation state
- streaming state
- UI state
- modal state
- approval state
- authentication state

Avoid putting everything into one global store.

---

# 31. API CONTRACTS

Before changing frontend API usage:

1. Inspect the backend endpoints.
2. Inspect request/response schemas.
3. Inspect streaming behavior.
4. Inspect authentication.
5. Inspect approval endpoints.
6. Inspect background-job endpoints.
7. Inspect citation/source structures.
8. Inspect agent/tool status structures.

Do not guess API contracts.

If an API lacks information required for a polished UI:

- determine whether the backend already exposes an equivalent field
- prefer adapting the frontend to existing contracts
- only modify backend contracts when genuinely necessary
- preserve backward compatibility where practical

---

# 32. SECURITY

Never:

- store secrets in frontend source
- expose backend credentials
- trust frontend authorization
- expose system prompts
- expose chain-of-thought
- expose hidden guardrail rules
- expose private document content
- expose another user's conversation
- expose internal tool credentials
- expose raw approval hashes
- expose sensitive telemetry

Security decisions remain server-side.

---

# 33. VISUAL QA WITH ANTIGRAVITY BROWSER

Whenever making significant frontend changes:

1. Start the application.
2. Open it using Antigravity Browser.
3. Inspect the actual rendered interface.
4. Test desktop.
5. Test narrow/mobile viewport behavior where possible.
6. Interact with major controls.
7. Inspect console/runtime errors.
8. Capture screenshots when useful.
9. Correct visual problems.
10. Re-test.

Use browser-based verification rather than assuming the implementation is correct.

Antigravity Browser can inspect and actuate Chrome and can capture screenshots and browser recordings.

---

# 34. REQUIRED VISUAL QA CHECKLIST

Test at minimum:

### Authentication
- login
- logout
- session expiration
- unauthorized route

### Conversations
- create conversation
- switch conversation
- rename
- delete/archive if supported
- reload and restore

### Chat
- send message
- multiline input
- streaming
- stop generation
- retry
- copy
- long response
- markdown
- code block
- table

### RAG
- source citations
- source expansion
- permission-denied behavior

### Agents
- agent activity
- tool activity
- workflow progress
- long-running job

### Approval
- approval card
- approve
- reject
- expired approval
- approval failure

### Errors
- API failure
- network failure
- tool failure
- background job failure

### Responsive
- desktop
- tablet
- mobile

### Accessibility
- keyboard navigation
- focus states
- reduced motion

---

# 35. VISUAL QUALITY BAR

Do not stop at:

"the UI works."

The target is:

"the UI feels finished."

Before declaring the frontend complete, inspect:

- alignment
- spacing
- typography
- consistency
- animation timing
- loading behavior
- empty states
- error states
- responsive behavior
- keyboard behavior
- visual hierarchy
- component consistency

Fix obvious polish issues proactively.

---

# 36. DO NOT OVERDESIGN

The interface should feel premium because it is:

- coherent
- fast
- restrained
- predictable
- polished

not because it contains:

- excessive gradients
- glowing borders
- huge animations
- floating particles
- unnecessary 3D effects
- excessive glassmorphism
- decorative backgrounds

Prefer product quality over visual spectacle.

---

# 37. BROWSER-VERIFIED DEVELOPMENT LOOP

For significant UI work, follow:

AUDIT
↓
PLAN
↓
IMPLEMENT
↓
RUN
↓
BROWSER INSPECT
↓
INTERACT
↓
CAPTURE
↓
IDENTIFY ISSUES
↓
REFINE
↓
RETEST
↓
FINAL QA

Do not declare completion immediately after editing code.

---

# 38. PRESERVE FUNCTIONALITY

Before changing any existing component, determine:

- what functionality it provides
- what API it calls
- what state it manages
- what permissions it assumes
- what routes depend on it
- what other components consume it

Visual refactoring must not accidentally remove functionality.

When replacing a component:

1. document its current behavior
2. preserve required behavior
3. improve presentation
4. test existing flows

---

# 39. FINAL PRODUCT PRINCIPLE

The user should experience:

"Just chat with it."

The complexity should emerge only when useful:

Simple question:
→ clean answer

Enterprise question:
→ answer + citations

Complex research:
→ activity + sources + answer

Agent workflow:
→ concise progress + final result

Sensitive external action:
→ approval card

Long-running workflow:
→ persistent progress

Error:
→ clear recovery path

The underlying platform may be extremely sophisticated.

The interface should remain calm.

---

# 40. DEFINITION OF DONE

Frontend transformation is NOT complete until:

- the application has a cohesive modern design system
- the chat experience feels like a modern AI product
- conversations feel persistent and polished
- streaming feels smooth
- messages render beautifully
- citations are intuitive
- tool/agent activity is understandable
- approvals are clear and secure
- errors are recoverable
- animations are polished but restrained
- mobile experience works
- accessibility is addressed
- dark/light themes work if supported
- no major console errors remain
- backend security is unchanged
- RBAC remains enforced server-side
- browser QA has been performed
- major user journeys have been tested
- the interface feels production-ready

The final standard is not:

"technically functional."

The final standard is:

"credible as a commercial AI product."