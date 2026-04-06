import { useEffect, useId, useState } from "react";

import type { SentenceTokenPreview } from "../../shared/api/generated/types.gen";

import { promptTypographyClass } from "./typography";

type HintableTokenProps = {
  isOpen: boolean;
  onDismiss: () => void;
  onToggle: () => void;
  token: SentenceTokenPreview;
};

function HintableToken(props: HintableTokenProps) {
  const { isOpen, onDismiss, onToggle, token } = props;
  const hints = token.hints ?? [];
  const hasHints = hints.length > 0;
  const tooltipId = useId();
  const [hovered, setHovered] = useState(false);
  const [focused, setFocused] = useState(false);

  if (!hasHints) {
    return <span>{token.surface}</span>;
  }

  /** Single visibility flag for both CSS and aria (pinned, hover, or keyboard focus). */
  const tooltipRevealed = isOpen || hovered || focused;

  return (
    <button
      aria-describedby={tooltipRevealed ? tooltipId : undefined}
      aria-expanded={tooltipRevealed}
      aria-label={`${token.surface}, hint available`}
      className="group/hint relative inline-block cursor-help border-0 bg-transparent p-0 pb-[5px] text-inherit transition-colors duration-100 hover:bg-[var(--lesson-accent)]/[0.07] focus-visible:outline-2 focus-visible:outline-[var(--lesson-accent)] focus-visible:outline-offset-2"
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
          setFocused(false);
          onDismiss();
        }
      }}
      onClick={() => {
        onToggle();
      }}
      onFocus={() => {
        setFocused(true);
      }}
      onMouseEnter={() => {
        setHovered(true);
      }}
      onMouseLeave={() => {
        setHovered(false);
      }}
      type="button"
    >
      {token.surface}
      <span
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-[3px] bottom-0 h-[2px] rounded-full bg-[var(--lesson-accent)] opacity-20 transition-opacity duration-100 group-focus-within/hint:opacity-50 group-hover/hint:opacity-50"
      />
      <span
        aria-hidden={!tooltipRevealed}
        className={`absolute top-full left-1/2 z-40 mt-2 -translate-x-1/2 rounded-xl border border-[var(--lesson-border-soft)] bg-white px-4 py-2.5 shadow-[0_8px_24px_rgba(22,28,37,0.08)] transition-opacity duration-100 ${
          tooltipRevealed ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0"
        }`}
        id={tooltipId}
        role="tooltip"
      >
        <span className="flex flex-col">
          {hints.map((hint, i) => (
            <span
              className={`whitespace-nowrap font-normal text-[0.9rem] text-[var(--lesson-text-soft)] leading-relaxed tracking-normal ${
                i > 0 ? "mt-1.5 border-[var(--lesson-border-soft)]/60 border-t pt-1.5" : ""
              }`}
              key={hint}
            >
              {hint}
            </span>
          ))}
        </span>
        <span className="absolute bottom-full left-1/2 -translate-x-1/2 border-[5px] border-transparent border-b-[var(--lesson-border-soft)]" />
        <span className="absolute bottom-full left-1/2 -translate-x-1/2 translate-y-px border-[5px] border-transparent border-b-white" />
      </span>
    </button>
  );
}

type HintablePromptProps = { promptText: string; tokens: Array<SentenceTokenPreview> };

export function HintablePrompt(props: HintablePromptProps) {
  const { promptText, tokens } = props;
  const hasAnyHints = tokens.some((t) => t.hints && t.hints.length > 0);
  const [openHintTokenIndex, setOpenHintTokenIndex] = useState<number | null>(null);

  useEffect(() => {
    if (openHintTokenIndex === null) {
      return;
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.stopPropagation();
        setOpenHintTokenIndex(null);
      }
    }
    window.addEventListener("keydown", onKeyDown, true);
    return () => {
      window.removeEventListener("keydown", onKeyDown, true);
    };
  }, [openHintTokenIndex]);

  if (!hasAnyHints || tokens.length === 0) {
    return (
      <h1 className={`text-balance text-[var(--lesson-text)] ${promptTypographyClass(promptText)}`}>
        {promptText}
      </h1>
    );
  }

  const hasSpaces = promptText.includes(" ");

  return (
    <h1 className={`text-[var(--lesson-text)] ${promptTypographyClass(promptText)}`}>
      {tokens.map((token, i) => (
        <span key={token.token_index}>
          {hasSpaces && i > 0 ? " " : null}
          <HintableToken
            isOpen={openHintTokenIndex === token.token_index}
            onDismiss={() => {
              setOpenHintTokenIndex(null);
            }}
            onToggle={() => {
              setOpenHintTokenIndex((prev) =>
                prev === token.token_index ? null : token.token_index,
              );
            }}
            token={token}
          />
        </span>
      ))}
    </h1>
  );
}
