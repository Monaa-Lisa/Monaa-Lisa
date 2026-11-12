/**
 * Reads a search text the way a person types it: several words in any
 * order ("vaswani attention"), or an arXiv id.
 */

/** More words than this are ignored, every word is one more index lookup */
const MAX_WORDS = 8;

/**
 * The words every result has to contain. Words of one or two letters are
 * left out when there are longer ones, the trigram indexes cannot look them
 * up and they hardly narrow a search ("is", "of", "a").
 */
export function searchWords(text: string): string[] {
  const words = [...new Set(text.toLowerCase().split(/[\s,;]+/))].filter(
    Boolean,
  );
  const long = words.filter((w) => w.length >= 3);
  return (long.length ? long : words).slice(0, MAX_WORDS);
}

/**
 * The arXiv id in a search text, or null: "1706.03762", "arXiv:1706.03762v5",
 * "hep-th/9711200" or a link to arxiv.org. The version is dropped, papers are
 * stored without it.
 */
export function arxivId(text: string): string | null {
  const match = text
    .trim()
    .match(
      /^(?:https?:\/\/arxiv\.org\/(?:abs|pdf)\/|arxiv:)?(\d{4}\.\d{4,5}|[a-z-]+(?:\.[a-z]{2})?\/\d{7})(?:v\d+)?(?:\.pdf)?$/i,
    );
  return match ? match[1] : null;
}
