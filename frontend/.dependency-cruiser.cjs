/** @type {import('dependency-cruiser').IConfiguration} */

/**
 * Layering (see STRUCTURE.md):
 *   shared → entities → features → pages/widgets → app
 *
 * - `shared` — infra only; no product slices above it.
 * - `entities` — domain helpers + small UI that is still “the noun”; no features.
 * - `features` — screens and orchestration; no sibling features except the documented
 *   exception: **kana may import lesson** (shared lesson chrome).
 * - `pages` — route adapters; may import features/entities/shared, not app/widgets.
 * - `widgets` — composed shells; may import features/entities/shared, not pages/app.
 * - `app` — router/providers; may import any layer.
 */

const FEATURE_TOP_LEVELS = ["account", "auth", "kana", "kanji", "lesson", "path"];

/** Other feature roots that `sourceFeat` must not import from. */
function forbiddenFeatureTargets(sourceFeat) {
  return FEATURE_TOP_LEVELS.filter((f) => {
    if (f === sourceFeat) return false;
    if (sourceFeat === "kana" && f === "lesson") return false;
    return true;
  });
}

const siblingFeatureRules = FEATURE_TOP_LEVELS.map((f) => {
  const targets = forbiddenFeatureTargets(f);
  return {
    name: `features-${f}-no-sibling-features`,
    severity: "error",
    comment: `src/features/${f}/ must not import other feature roots (use entities/ or shared/; kana may import lesson).`,
    from: { path: `^src/features/${f}/` },
    to: { path: `^src/features/(${targets.join("|")})/` },
  };
});

module.exports = {
  forbidden: [
    {
      name: "shared-no-higher-layers",
      severity: "error",
      comment:
        "shared is the lowest layer — must not import entities, features, widgets, pages, or app (see STRUCTURE.md).",
      from: { path: "^src/shared" },
      to: { path: "^src/(entities|features|widgets|pages|app)/" },
    },
    {
      name: "entities-no-features-or-above",
      severity: "error",
      comment: "entities may import shared and other entities only.",
      from: { path: "^src/entities" },
      to: { path: "^src/(features|widgets|pages|app)/" },
    },
    {
      name: "features-no-widgets-pages-app",
      severity: "error",
      comment: "features may import entities and shared only (not widgets, pages, or app).",
      from: { path: "^src/features" },
      to: { path: "^src/(widgets|pages|app)/" },
    },
    ...siblingFeatureRules,
    {
      name: "widgets-no-pages-app",
      severity: "error",
      comment: "widgets may import features, entities, and shared only.",
      from: { path: "^src/widgets" },
      to: { path: "^src/(pages|app)/" },
    },
    {
      name: "pages-no-app-or-widgets",
      severity: "error",
      comment:
        "pages are route adapters — import features/entities/shared only (not app or widgets).",
      from: { path: "^src/pages" },
      to: { path: "^src/(app|widgets)/" },
    },
  ],
  options: {
    tsPreCompilationDeps: true,
    exclude: {
      path: "(^|/)node_modules/|\\.test\\.[jt]sx?$|^src/test/|^src/shared/api/generated/",
    },
  },
};
