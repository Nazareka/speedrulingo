import { useEffect, useId, useState } from "react";

import type { SentenceTokenPreview } from "../../../shared/api/generated/types.gen";

import { promptTypographyClass } from "../model/typography";

type HintableTokenProps = {
  isOpen: boolean;
  onDismiss: () => void;
  onPlayAudio?: (() => void) | undefined;
  onToggle: () => void;
  token: SentenceTokenPreview;
};

function HintableToken(props: HintableTokenProps) {
  const { isOpen, onDismiss, onPlayAudio, onToggle, token } = props;
  const hints = token.hints ?? [];
  const hasHints = hints.length > 0;
  const hasAudio = token.word_audio_url != null;
  const isInteractive = hasHints || hasAudio;
  const tooltipId = useId();
  const [hovered, setHovered] = useState(false);
  const [focused, setFocused] = useState(false);

  if (!isInteractive) {
    return <span>{token.surface}</span>;
  }

  /** Single visibility flag for both CSS and aria (pinned, hover, or keyboard focus). */
  const tooltipRevealed = isOpen || hovered || focused;

  return (
    <button
      aria-describedby={hasHints && tooltipRevealed ? tooltipId : undefined}
      aria-expanded={hasHints ? tooltipRevealed : undefined}
      aria-label={
        hasHints && hasAudio
          ? `${token.surface}, hint and audio available`
          : hasHints
            ? `${token.surface}, hint available`
            : `${token.surface}, audio available`
      }
      className={`group/hint relative inline-block border-0 bg-transparent p-0 pb-[5px] text-inherit transition-colors duration-100 hover:bg-[var(--lesson-accent)]/[0.07] focus-visible:outline-2 focus-visible:outline-[var(--lesson-accent)] focus-visible:outline-offset-2 ${
        hasAudio ? "cursor-pointer" : "cursor-help"
      }`}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
          setFocused(false);
          onDismiss();
        }
      }}
      onClick={() => {
        onPlayAudio?.();
        if (hasHints) {
          onToggle();
        }
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
        className={`pointer-events-none absolute inset-x-[3px] bottom-0 h-[2px] rounded-full bg-[var(--lesson-accent)] transition-opacity duration-100 group-focus-within/hint:opacity-50 group-hover/hint:opacity-50 ${
          hasAudio ? "opacity-45" : "opacity-20"
        }`}
      />
      {hasHints ? (
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
      ) : null}
    </button>
  );
}

type HintablePromptProps = {
  onPlayTokenAudio?: ((audioUrl: string) => void) | undefined;
  promptText: string;
  tokens: Array<SentenceTokenPreview>;
};

export function HintablePrompt(props: HintablePromptProps) {
  const { onPlayTokenAudio, promptText, tokens } = props;
  const hasAnyInteractiveTokens = tokens.some(
    (t) => (t.hints && t.hints.length > 0) || t.word_audio_url != null,
  );
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

  if (!hasAnyInteractiveTokens || tokens.length === 0) {
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
          {(() => {
            const audioUrl = token.word_audio_url;
            return (
              <HintableToken
                isOpen={openHintTokenIndex === token.token_index}
                onDismiss={() => {
                  setOpenHintTokenIndex(null);
                }}
                onPlayAudio={
                  audioUrl == null
                    ? undefined
                    : () => {
                        onPlayTokenAudio?.(audioUrl);
                      }
                }
                onToggle={() => {
                  setOpenHintTokenIndex((prev) =>
                    prev === token.token_index ? null : token.token_index,
                  );
                }}
                token={token}
              />
            );
          })()}
        </span>
      ))}
    </h1>
  );
}
