import { describe, expect, it } from "vitest";
import type { KanaOverviewResponse } from "../../../shared/api/generated/types.gen";
import {
  buildKanaGroupRows,
  buildKanaScriptSections,
  characterProgressPercent,
  flattenKanaCharacters,
  isKanaOverviewTileTappable,
  kanaOverviewTileClassName,
  masteryPercent,
} from "./kana-model";

const overview: KanaOverviewResponse = {
  current_lesson_id: null,
  total_characters: 4,
  mastered_characters: 1,
  scripts: [
    {
      script: "hiragana",
      characters: [
        {
          character_id: "a",
          char: "あ",
          audio_url: "/audio/a",
          script: "hiragana",
          group_key: "vowels",
          times_seen: 6,
          target_exposures: 6,
          state: "mastered",
        },
      ],
    },
    {
      script: "katakana",
      characters: [
        {
          character_id: "ka",
          char: "カ",
          audio_url: "/audio/ka",
          script: "katakana",
          group_key: "k",
          times_seen: 2,
          target_exposures: 6,
          state: "learning",
        },
      ],
    },
  ],
};

const masteredCharacter = overview.scripts[0]?.characters[0];

describe("masteryPercent", () => {
  it("calculates overview mastery ratio", () => {
    expect(masteryPercent(overview)).toBe(25);
  });
});

describe("characterProgressPercent", () => {
  it("caps progress at 100", () => {
    if (!masteredCharacter) {
      throw new Error("Missing mastered character fixture");
    }
    expect(characterProgressPercent(masteredCharacter)).toBe(100);
  });
});

describe("flattenKanaCharacters", () => {
  it("flattens both scripts into one list", () => {
    expect(flattenKanaCharacters(overview)).toHaveLength(2);
  });
});

describe("buildKanaScriptSections", () => {
  it("places hiragana and katakana in separate sections with phonetic subgroups", () => {
    const sections = buildKanaScriptSections(overview);
    expect(sections).toHaveLength(2);
    expect(sections[0]?.script).toBe("hiragana");
    expect(sections[0]?.subgroups[0]?.groupKey).toBe("vowels");
    expect(sections[1]?.script).toBe("katakana");
    expect(sections[1]?.subgroups[0]?.groupKey).toBe("k");
  });
});

describe("buildKanaGroupRows", () => {
  it("aligns phonetic groups into rows with separate hiragana and katakana columns", () => {
    const rows = buildKanaGroupRows(overview);
    expect(rows).toHaveLength(2);
    expect(rows[0]?.groupKey).toBe("vowels");
    expect(rows[0]?.hiragana).toHaveLength(1);
    expect(rows[0]?.katakana).toHaveLength(0);
    expect(rows[1]?.groupKey).toBe("k");
    expect(rows[1]?.hiragana).toHaveLength(0);
    expect(rows[1]?.katakana).toHaveLength(1);
  });
});

describe("kanaOverviewTileClassName", () => {
  it("styles upcoming planned lesson targets as sky", () => {
    expect(
      kanaOverviewTileClassName({
        character_id: "x",
        char: "さ",
        script: "hiragana",
        group_key: "s",
        times_seen: 0,
        target_exposures: 6,
        state: "new",
        is_next_lesson_new: true,
      }),
    ).toContain("sky-");
  });
});

describe("isKanaOverviewTileTappable", () => {
  it("is tappable when the API provided audio_url", () => {
    expect(
      isKanaOverviewTileTappable({
        character_id: "x",
        char: "さ",
        script: "hiragana",
        group_key: "s",
        times_seen: 0,
        target_exposures: 6,
        state: "new",
        audio_url: "/api/v1/kana/audio/x",
      }),
    ).toBe(true);
  });

  it("is not tappable when audio_url is missing", () => {
    expect(
      isKanaOverviewTileTappable({
        character_id: "x",
        char: "さ",
        script: "hiragana",
        group_key: "s",
        times_seen: 0,
        target_exposures: 6,
        state: "new",
      }),
    ).toBe(false);
  });
});
