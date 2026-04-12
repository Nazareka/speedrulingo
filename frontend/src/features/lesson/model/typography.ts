function isLikelyJapaneseText(text: string) {
  return /[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff]/u.test(text);
}

export function optionTypographyClass(text: string) {
  return isLikelyJapaneseText(text)
    ? "font-['Noto_Sans_JP','Hiragino_Sans','Yu_Gothic','Meiryo',sans-serif] text-[1.24rem] leading-7"
    : "text-[1.16rem] leading-7";
}

export function promptTypographyClass(text: string) {
  return isLikelyJapaneseText(text)
    ? "font-['Noto_Sans_JP','Hiragino_Sans','Yu_Gothic','Meiryo',sans-serif] text-[2.2rem] font-semibold leading-[1.22] tracking-[-0.035em] md:text-[2.9rem]"
    : "text-[1.8rem] font-semibold leading-[1.1] tracking-[-0.04em] md:text-[2.4rem]";
}
