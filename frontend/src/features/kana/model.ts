import type {
  KanaCharacterProgress,
  KanaOverviewResponse,
} from "../../shared/api/generated/types.gen";

/** One phonetic family (e.g. vowels, K row) inside a script section. */
export type KanaSubgroupVm = {
  groupKey: string;
  label: string;
  characters: KanaCharacterProgress[];
};

/** Hiragana or katakana block with nested families. */
export type KanaScriptSectionVm = {
  script: "hiragana" | "katakana";
  title: string;
  subgroups: KanaSubgroupVm[];
};

/** One phonetic family with both scripts on the same row (for side-by-side layout). */
export type KanaGroupRowVm = {
  groupKey: string;
  label: string;
  hiragana: KanaCharacterProgress[];
  katakana: KanaCharacterProgress[];
};

const GROUP_LABELS: Record<string, string> = {
  vowels: "Vowels",
  k: "K row",
  s: "S row",
  t: "T row",
  n: "N row",
  h: "H row",
  m: "M row",
  y: "Y row",
  r: "R row",
  w: "W row",
  g: "G row",
  z: "Z row",
  d: "D row",
  b: "B row",
  p: "P row",
  vu: "Vu",
};

export function masteryPercent(overview: KanaOverviewResponse): number {
  if (overview.total_characters <= 0) {
    return 0;
  }
  return Math.round((overview.mastered_characters / overview.total_characters) * 100);
}

export function characterProgressPercent(character: KanaCharacterProgress): number {
  if (character.target_exposures <= 0) {
    return 0;
  }
  return Math.min(100, Math.round((character.times_seen / character.target_exposures) * 100));
}

/** Visual style for one cell on /kana (mirrors backend `state` + `is_next_lesson_new`). */
export function kanaOverviewTileClassName(character: KanaCharacterProgress): string {
  const { state, is_next_lesson_new: upcoming } = character;
  if (state === "locked") {
    return "border-stone-200 bg-stone-100 text-stone-400";
  }
  if (state === "mastered") {
    return "border-emerald-300 bg-emerald-50 text-emerald-700";
  }
  if (upcoming === true) {
    return "border-sky-300 bg-sky-50 text-sky-700";
  }
  if (state === "learning") {
    return "border-amber-300 bg-amber-50 text-amber-700";
  }
  if (state === "new") {
    return "border-stone-200 bg-stone-100 text-stone-400";
  }
  return "border-stone-200 bg-stone-100 text-stone-400";
}

/** Tile is interactive when the API provided a pronunciation URL (missing asset → no tap). */
export function isKanaOverviewTileTappable(character: KanaCharacterProgress): boolean {
  return Boolean(character.audio_url);
}

export function flattenKanaCharacters(overview: KanaOverviewResponse): KanaCharacterProgress[] {
  return overview.scripts.flatMap((group) => group.characters);
}

export function buildKanaScriptSections(overview: KanaOverviewResponse): KanaScriptSectionVm[] {
  const sections: KanaScriptSectionVm[] = [];
  for (const scriptGroup of overview.scripts) {
    const byKey = new Map<string, KanaSubgroupVm>();
    const keyOrder: string[] = [];
    for (const character of scriptGroup.characters) {
      let subgroup = byKey.get(character.group_key);
      if (subgroup === undefined) {
        keyOrder.push(character.group_key);
        subgroup = {
          groupKey: character.group_key,
          label: GROUP_LABELS[character.group_key] ?? character.group_key,
          characters: [],
        };
        byKey.set(character.group_key, subgroup);
      }
      subgroup.characters.push(character);
    }
    const orderedSubgroups: KanaSubgroupVm[] = [];
    for (const key of keyOrder) {
      const entry = byKey.get(key);
      if (entry !== undefined) {
        orderedSubgroups.push(entry);
      }
    }
    sections.push({
      script: scriptGroup.script,
      title: scriptGroup.script === "hiragana" ? "Hiragana" : "Katakana",
      subgroups: orderedSubgroups,
    });
  }
  return sections;
}

export function buildKanaGroupRows(overview: KanaOverviewResponse): KanaGroupRowVm[] {
  const sections = buildKanaScriptSections(overview);
  const hiragana = sections.find((s) => s.script === "hiragana");
  const katakana = sections.find((s) => s.script === "katakana");
  const byKeyH = new Map((hiragana?.subgroups ?? []).map((g) => [g.groupKey, g]));
  const byKeyK = new Map((katakana?.subgroups ?? []).map((g) => [g.groupKey, g]));

  const keyOrder: string[] = [];
  const seen = new Set<string>();
  for (const g of hiragana?.subgroups ?? []) {
    if (!seen.has(g.groupKey)) {
      seen.add(g.groupKey);
      keyOrder.push(g.groupKey);
    }
  }
  for (const g of katakana?.subgroups ?? []) {
    if (!seen.has(g.groupKey)) {
      seen.add(g.groupKey);
      keyOrder.push(g.groupKey);
    }
  }

  return keyOrder.map((groupKey) => {
    const h = byKeyH.get(groupKey);
    const k = byKeyK.get(groupKey);
    const label = h?.label ?? k?.label ?? GROUP_LABELS[groupKey] ?? groupKey;
    return {
      groupKey,
      label,
      hiragana: h?.characters ?? [],
      katakana: k?.characters ?? [],
    };
  });
}
