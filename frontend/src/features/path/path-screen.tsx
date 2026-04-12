import { findSectionById, isCourseFullyCompleted } from "../../entities/path/model";
import { usePathPageState } from "./model/use-path-page-state";
import { AllUnitsPicker, SectionPicker } from "./ui/path-pickers";
import { PathUnitGuidePanel } from "./ui/path-unit-guide-panel";
import { UnitCarousel } from "./ui/unit-carousel";

/** Path overview + unit carousel (route layer has no params). */
export function PathScreen() {
  const {
    pathQuery,
    currentCourseQuery,
    activeUnitId,
    effectiveSelection,
    pathSlides,
    allUnitsFlat,
    guideUnitId,
    guideUnitQuery,
    handleSelectSection,
    handlePickUnitFromAll,
    handleCarouselUnitChange,
  } = usePathPageState();

  if (pathQuery.isLoading || currentCourseQuery.isLoading) {
    return (
      <div className="pt-4">
        <div className="mx-auto max-w-6xl space-y-6">
          <div className="h-28 animate-pulse rounded-[1.6rem] bg-[var(--lesson-surface-muted)]" />
          <div className="h-72 animate-pulse rounded-[1.6rem] bg-[var(--lesson-surface-muted)]" />
          <div className="grid gap-4 md:grid-cols-2">
            <div className="h-56 animate-pulse rounded-[1.6rem] bg-[var(--lesson-surface-muted)]" />
            <div className="h-56 animate-pulse rounded-[1.6rem] bg-[var(--lesson-surface-muted)]" />
          </div>
        </div>
      </div>
    );
  }

  if (!pathQuery.data || !currentCourseQuery.data) {
    return (
      <div className="pt-4 text-[var(--lesson-text-muted)]">
        <div className="mx-auto max-w-6xl rounded-[1.6rem] border border-[var(--lesson-border)] bg-[var(--lesson-surface)] p-6">
          No active course is available yet.
        </div>
      </div>
    );
  }

  const pathData = pathQuery.data;
  const allUnitsInCourseCompleted = isCourseFullyCompleted(pathData);

  const currentLessonId = pathData.current_lesson_id ?? null;

  const courseSections = pathData.sections;
  const selectedSectionId = effectiveSelection?.selectedSectionId ?? null;
  const currentSection = findSectionById(pathData, selectedSectionId);

  return (
    <div className="font-['Inter','SF_Pro_Display','SF_Pro_Text','Geist',system-ui,sans-serif] text-[var(--lesson-text)]">
      <main className="mx-auto w-full max-w-6xl py-5">
        <div className="space-y-4">
          <header>
            <h1 className="font-semibold text-2xl tracking-[-0.03em] md:text-3xl">Your path</h1>
            <p className="mt-1 text-[var(--lesson-text-muted)] text-sm">
              Pick up where you left off.
            </p>
          </header>

          <div className="w-full min-w-0 space-y-2">
            {courseSections.length > 0 ? (
              <div className="w-full min-w-0 md:grid md:grid-cols-2 md:items-start md:gap-x-8">
                <div className="grid min-w-0 grid-cols-2 gap-2">
                  <div className="min-w-0">
                    <SectionPicker
                      currentSectionId={selectedSectionId}
                      onSelectSection={handleSelectSection}
                      sections={courseSections}
                    />
                  </div>
                  <div className="min-w-0">
                    <AllUnitsPicker
                      allUnits={allUnitsFlat}
                      highlightedUnitId={effectiveSelection?.selectedUnitId ?? null}
                      onSelectUnit={handlePickUnitFromAll}
                    />
                  </div>
                </div>
                <div aria-hidden="true" className="hidden min-h-0 md:block" />
              </div>
            ) : null}
          </div>

          <UnitCarousel
            activeUnitId={activeUnitId}
            currentLessonId={currentLessonId}
            fallbackBody={
              allUnitsInCourseCompleted
                ? "You've completed every lesson. Browse units in the carousel below."
                : "No active unit yet. Choose a section to browse units."
            }
            fallbackTitle={`${currentCourseQuery.data.course_code} · v${currentCourseQuery.data.course_version}`}
            onUnitChange={handleCarouselUnitChange}
            selectedUnitId={effectiveSelection?.selectedUnitId ?? null}
            sidePanel={
              <aside aria-label="Unit guide for the selected unit">
                <PathUnitGuidePanel guideUnitId={guideUnitId} guideUnitQuery={guideUnitQuery} />
              </aside>
            }
            slides={pathSlides}
          />

          <section className="rounded-[1.4rem] border border-[var(--lesson-border)] bg-[var(--lesson-surface-muted)] p-3 md:p-4">
            <p className="font-semibold text-[var(--lesson-text)] text-base leading-snug">
              {currentSection?.title ?? "Section"}
            </p>
            {currentSection?.description.trim() ? (
              <p className="mt-2 text-[var(--lesson-text-muted)] text-sm leading-relaxed">
                {currentSection.description}
              </p>
            ) : null}
          </section>
        </div>
      </main>
    </div>
  );
}
