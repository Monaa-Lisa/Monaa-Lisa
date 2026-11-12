/** Escapes % and _ so user input matches literally inside a LIKE / ILIKE pattern. */
export function containsPattern(term: string): string {
  return `%${term.replace(/[\\%_]/g, (c) => `\\${c}`)}%`;
}
