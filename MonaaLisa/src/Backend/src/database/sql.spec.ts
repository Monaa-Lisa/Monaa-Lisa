import { containsPattern } from './sql';

describe('containsPattern', () => {
  it('wraps the term for a substring match', () => {
    expect(containsPattern('graph')).toBe('%graph%');
  });

  it('escapes LIKE wildcards so they match literally', () => {
    expect(containsPattern('50%_off\\')).toBe('%50\\%\\_off\\\\%');
  });
});
