As a staff engineer, I would treat those folders as layers with clear responsibility boundaries, not just as “places to put files.”

Your current top-level split is already pretty reasonable:
	•	app
	•	pages
	•	features
	•	shared
	•	test

But the real value comes from defining what is allowed where.

The mental model

I usually prefer this direction:
	•	app = application shell and global wiring
	•	pages = route-level composition
	•	features = business use cases and user actions
	•	shared = reusable primitives, utilities, and low-level infrastructure
	•	test = cross-project test setup and helpers

That is a strong baseline for a medium-to-large React app.

⸻

Recommended responsibility of each folder

app

This is the composition root of the frontend.

It should contain things that initialize or wire the whole app together.

Typical contents:
	•	app entrypoint
	•	router creation
	•	query client creation
	•	providers
	•	global styles
	•	app-wide config
	•	auth/session bootstrapping
	•	error boundaries
	•	layout shell that is truly global
	•	app initialization logic

Examples:
	•	app/main.tsx
	•	app/router.tsx
	•	app/providers.tsx
	•	app/query-client.ts
	•	app/styles.css
	•	app/error-boundary.tsx

What should not go here:
	•	page-specific UI
	•	domain/business logic
	•	reusable feature logic
	•	random helper functions

Rule of thumb: if it exists because “the whole app needs this wired together,” it belongs in app.

⸻

pages

This should contain route-level screens.

A page should mostly do orchestration:
	•	read route params
	•	read search params
	•	trigger page-level loaders if needed
	•	compose several features/widgets together
	•	define layout specific to that route
	•	keep minimal logic

A page is not where you want a lot of business logic to live.

Good page example:
	•	pages/lesson/ui/lesson-page.tsx
	•	pages/settings/ui/settings-page.tsx

A page should sound like:

“To render this route, I combine feature A, feature B, and shared layout C.”

Bad page example:
	•	page directly calling APIs
	•	page containing big forms with all validation logic inline
	•	page manually transforming server DTOs into UI models everywhere
	•	page containing business rules like unlock logic, submission rules, permission logic

That kind of code belongs lower.

⸻

features

This is the most important folder.

A feature should represent a user-visible capability or business action.

Examples:
	•	sign in
	•	update profile
	•	submit answer
	•	change lesson step
	•	complete unit
	•	create course version
	•	review previous lesson
	•	search words

A feature can contain:
	•	UI specific to that feature
	•	hooks
	•	actions/mutations
	•	validation schemas
	•	small local state
	•	feature-specific API calls
	•	adapters/mappers if needed
	•	feature tests

Example:

features/
  submit-answer/
    ui/
      submit-answer-button.tsx
      answer-feedback.tsx
    model/
      use-submit-answer.ts
      submit-answer.schema.ts
      types.ts
    api/
      submit-answer.ts
    lib/
      map-answer-payload.ts

This is where most business logic should live.

A feature should be independently understandable:
	•	what user action it supports
	•	what state it manages
	•	what data it reads/writes
	•	what UI pieces it exposes

What should not go here:
	•	generic button/input/modal components
	•	app-wide providers
	•	generic utilities
	•	arbitrary route containers

⸻

shared

This is where teams often make a mess, so it needs strict discipline.

shared is for things that are:
	•	reusable
	•	not tied to one feature
	•	low-level
	•	business-agnostic or nearly so

Typical subfolders:
	•	shared/ui — reusable UI primitives
	•	shared/lib — utilities
	•	shared/api — API client base, common request helpers
	•	shared/config — environment/config helpers
	•	shared/types — common types
	•	shared/hooks — generic hooks
	•	shared/constants — generic constants
	•	shared/assets — icons/images/fonts

Examples:
	•	Button, Dialog, ProgressBar
	•	cn, date formatting helpers, invariant helpers
	•	API client instance from @hey-api/client-fetch
	•	zod helpers
	•	useDebounce, usePrevious
	•	generic ApiError

What should not go into shared:
	•	lesson unlock rules
	•	user progress logic
	•	“temporary utils” that are actually feature-specific
	•	components that are only reused because two pages happen to need the same business widget

Important distinction:
	•	shared/ui/Button → yes
	•	shared/ui/LessonAnswerCard → probably no, unless it is truly generic
	•	shared/lib/formatDate → yes
	•	shared/lib/calculateLessonScore → usually no, that belongs to a feature/domain layer

If something contains business vocabulary, it usually should not be in shared.

⸻

test

Use this for test infrastructure, not necessarily all tests.

Good things to keep here:
	•	test setup
	•	test utils
	•	custom render helpers
	•	mocks/fakes
	•	MSW handlers
	•	fixtures shared across multiple features
	•	Vitest global setup

Examples:
	•	test/setup.ts
	•	test/render.tsx
	•	test/msw/server.ts
	•	test/fixtures/user.ts

I would not centralize every test file here.

Usually better:
	•	keep unit/feature tests close to code
	•	use test/ only for shared testing infrastructure

So:
	•	features/login/model/use-login.test.ts
	•	shared/lib/date.test.ts
	•	plus global stuff in test/

That scales better.

⸻

Folders I would probably add

Your current structure is good, but for a serious app I would strongly consider adding one or two of these.

entities

This is useful if the app has rich domain objects that appear across many features.

Examples:
	•	user
	•	lesson
	•	unit
	•	course
	•	word
	•	sentence
	•	session

This folder holds the domain representation, not actions.

Typical contents:
	•	types
	•	entity-level hooks
	•	selectors
	•	tiny display components
	•	mappers from API DTO to app model

Example:

entities/
  lesson/
    model/
      types.ts
      lesson.ts
      lesson.selectors.ts
    api/
      lesson.query.ts
    ui/
      lesson-badge.tsx
      lesson-status-chip.tsx

Why this helps:

Without entities, teams often put everything into either features or shared, and both become muddy.

Use entities when:
	•	several features depend on the same domain object
	•	you want a clear separation between “thing” and “action on the thing”

For a non-trivial product, I usually like:
	•	entities = nouns
	•	features = verbs

That is a very useful distinction.

⸻

widgets

This is optional, but useful when pages are composed from larger UI blocks.

A widget is a page section made of several entities/features/shared components.

Examples:
	•	lesson header
	•	sidebar navigation
	•	dashboard summary panel
	•	course overview block

This is not business action, and not a whole route either.

Example:

widgets/
  lesson-header/
  course-sidebar/
  profile-summary/

When it helps:
	•	pages are becoming large
	•	you need reusable route-level chunks
	•	pages starts filling with giant JSX blocks

If your app is still moderate, you can skip widgets for now.

⸻

processes or flows

Only if you truly have multi-step cross-feature workflows.

Examples:
	•	onboarding flow
	•	checkout
	•	signup wizard
	•	multi-step course builder run

Most teams do not need this folder early.

Only add it if you clearly have long-lived flows that coordinate multiple features/entities/pages.

⸻

Structure I would personally recommend

For your kind of stack, I would probably use this:

src/
  app/
    providers/
    router/
    styles/
    config/
    main.tsx

  pages/
    lesson/
    settings/
    dashboard/

  widgets/
    lesson-header/
    sidebar/
    dashboard-summary/

  features/
    auth/
    submit-answer/
    complete-lesson/
    update-profile/

  entities/
    user/
    lesson/
    unit/
    course/

  shared/
    api/
    ui/
    lib/
    hooks/
    config/
    types/
    assets/

  test/
    setup/
    mocks/
    fixtures/

If the app is smaller, remove widgets and entities and keep:

src/
  app/
  pages/
  features/
  shared/
  test/

That is still good.

⸻

Dependency rules I would enforce

Folder structure matters less than import rules.

A clean version would be:
	•	app can import from anywhere
	•	pages can import from features, entities, widgets, shared
	•	widgets can import from features, entities, shared
	•	features can import from entities, shared
	•	entities can import from shared
	•	shared can import only from shared

And never the reverse.

So:
	•	shared must not import features
	•	entities must not import pages
	•	features should not import pages
	•	pages should not be reused as components elsewhere

This matters more than naming.

⸻

How I would define each layer in one sentence
	•	app: bootstraps and wires the application
	•	pages: route screens that compose things
	•	widgets: large reusable screen sections
	•	features: user actions and business capabilities
	•	entities: domain objects and their representation
	•	shared: generic reusable building blocks
	•	test: testing infrastructure

⸻

Example with your stack

Given your dependencies, I would expect something like:

In shared
	•	Radix wrappers
	•	reusable dialog/progress primitives
	•	lucide icon helpers
	•	generic form fields
	•	zod helper utilities
	•	query helpers
	•	API client from @hey-api/client-fetch

In features
	•	react-hook-form forms
	•	mutation hooks with React Query
	•	form validation schemas
	•	submission logic
	•	action-specific UI

In pages
	•	TanStack Router route components
	•	route param handling
	•	composition of widgets/features

In app
	•	RouterProvider
	•	QueryClientProvider
	•	global error boundary
	•	root layout

⸻

Common mistakes

1. shared becomes “dumping ground”

This is the most common failure.

Fix:
only put things there if they are genuinely generic.

2. pages become giant smart components

Then route files turn into unmaintainable blobs.

Fix:
pages should compose, not own all logic.

3. features become too technical instead of business-oriented

Example:
	•	features/forms
	•	features/modals
	•	features/hooks

Those are not features. Those are implementation categories.

Better:
	•	features/login
	•	features/create-course
	•	features/submit-answer

4. API code scattered everywhere

Then every page and feature talks to backend differently.

Fix:
have a consistent API access pattern.

5. No import boundaries

Then even a nice folder tree rots quickly.

Fix:
enforce boundaries with ESLint or code review discipline.

⸻

My practical recommendation for you

For a real project, I would choose one of these two.

Option A — simpler, good default

src/
  app/
  pages/
  features/
  shared/
  test/

Use this if the app is still medium-sized.

Option B — more scalable

src/
  app/
  pages/
  widgets/
  features/
  entities/
  shared/
  test/

Use this if:
	•	domain is serious
	•	many screens reuse same domain objects
	•	app will grow for a while
	•	multiple developers will touch it

As a staff engineer, I would likely start with Option B only if I already know the product is substantial. Otherwise I would start with Option A, but leave room to introduce entities and widgets later.

⸻

Final opinion

Your current folders are not bad at all.
But I would tighten them like this:
	•	keep app
	•	keep pages
	•	keep features
	•	keep shared
	•	keep test
	•	add entities when domain objects start being reused across many features
	•	add widgets when pages become composition-heavy

The most important part is not adding more folders.
It is making sure each folder answers a different question:
	•	app — how is the application wired?
	•	pages — what route is this?
	•	features — what can the user do?
	•	entities — what thing does the app know about?
	•	shared — what is generic enough to reuse anywhere?

That separation usually gives the cleanest long-term frontend architecture.

I can also sketch a concrete folder tree for a sample app, like auth + dashboard + lesson flow, using exactly your stack.
